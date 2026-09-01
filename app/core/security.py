"""인증 · 인가 · 남용 방지.

세 가지를 담당한다:
  1. 사용자 인증 — 비밀번호 해싱(scrypt)과 세션 쿠키 발급/검증.
  2. 관리자 보호 — /admin/* 는 크롤·재색인을 트리거하므로 토큰을 요구한다.
  3. 레이트 리밋 — /chat/* 은 매 호출이 유료 LLM을 태우고, 로그인은
     무차별 대입 대상이다.

비밀번호는 stdlib의 hashlib.scrypt 를 쓴다. scrypt 는 메모리 하드 KDF로
OWASP 권장 목록에 있고, 외부 의존성 없이 쓸 수 있다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db


# ---------------- 관리자 토큰 ----------------
def require_admin(x_admin_token: str = Header(default="")) -> None:
    """X-Admin-Token 헤더를 settings.admin_token 과 대조한다.

    개발 모드에서 토큰이 비어 있으면 통과시킨다(로컬 편의). 운영 모드는
    config._require_production_settings 가 빈 토큰으로는 부팅 자체를 막으므로
    이 완화가 운영에 새지 않는다.
    """
    expected = settings.admin_token
    if not expected:
        if settings.is_production:  # 방어적 이중화: 여기까지 오면 설정 사고다
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ADMIN_TOKEN 미설정")
        return
    # 타이밍 공격 방지를 위해 상수시간 비교
    if not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "관리자 토큰이 올바르지 않습니다.")


# ---------------- 레이트 리밋 ----------------
# ponytail: 프로세스 메모리 카운터라 인스턴스마다 따로 센다. 인스턴스 N대면
# 실효 상한은 N배가 된다. 정확한 전역 상한이 필요해지면 Redis 토큰버킷으로 교체.
_HITS: dict[str, deque[float]] = defaultdict(deque)
_WINDOW_SEC = 60.0


def _client_key(request: Request) -> str:
    # 프록시/로드밸런서 뒤에 있으면 X-Forwarded-For 의 첫 홉이 실제 클라이언트다.
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_chat(request: Request) -> None:
    """분당 호출 상한. 초과 시 429."""
    limit = settings.chat_rate_limit_per_min
    if limit <= 0:  # 0 이하면 비활성화
        return

    key = _client_key(request)
    now = time.monotonic()
    hits = _HITS[key]
    while hits and now - hits[0] > _WINDOW_SEC:
        hits.popleft()

    if len(hits) >= limit:
        retry_after = int(_WINDOW_SEC - (now - hits[0])) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"요청이 너무 잦습니다. {retry_after}초 후 다시 시도해 주세요.",
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now)


def _reset_rate_limit() -> None:
    """테스트용: 카운터 초기화."""
    _HITS.clear()


# ---------------- 비밀번호 ----------------
# scrypt 파라미터. r=8, p=1 은 OWASP 권장 조합이고 N만 비용을 결정한다.
# N을 키울수록 안전하지만 로그인 응답이 그만큼 느려진다(동기 엔드포인트라
# 워커를 그동안 붙잡는다). settings.scrypt_n 으로 조정한다.
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
# n=2**17 까지 감당하려면 기본 maxmem(=32MB)으로는 부족하다.
_SCRYPT_MAXMEM = 256 * 1024 * 1024

MIN_PASSWORD_LENGTH = 8
# bcrypt 같은 72바이트 제한은 없지만, 무한정 긴 입력이 CPU를 태우지 않게 막는다.
MAX_PASSWORD_LENGTH = 200

# 배달 가능성까지 검증하지는 않는다(메일 발송 기능이 아직 없다).
# 공백·다중 @ 같은 명백한 오입력만 거른다.
# ponytail: email-validator 의존성 대신 정규식. 비밀번호 재설정 메일을
# 붙일 때 실제 발송으로 검증이 승격되므로 그때 재검토.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_EMAIL_LENGTH = 200


def normalize_email(email: str) -> str:
    """대소문자·앞뒤 공백만 다른 중복 가입을 막기 위해 정규화한다."""
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return len(email) <= MAX_EMAIL_LENGTH and bool(_EMAIL_RE.match(email))


def hash_password(password: str) -> str:
    """scrypt 해시를 'scrypt$n$r$p$salt$hash' 형식으로 만든다.

    파라미터를 해시에 함께 담아, 나중에 N을 올려도 기존 해시를 그대로
    검증할 수 있게 한다(형식을 바꾸면 전원 재설정해야 한다).
    """
    n = settings.scrypt_n
    salt = os.urandom(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=_SCRYPT_R, p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN, maxmem=_SCRYPT_MAXMEM,
    )
    b64 = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"scrypt${n}${_SCRYPT_R}${_SCRYPT_P}${b64(salt)}${b64(dk)}"


def verify_password(password: str, stored: str | None) -> bool:
    """상수시간 비교. 형식이 깨졌거나 계정에 비밀번호가 없으면 False."""
    if not stored:
        return False
    try:
        scheme, n_s, r_s, p_s, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt,
            n=int(n_s), r=int(r_s), p=int(p_s),
            dklen=len(expected), maxmem=_SCRYPT_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# ---------------- 세션 ----------------
def _hash_token(raw: str) -> str:
    """세션 토큰은 원문을 저장하지 않는다. DB 유출 시 재사용을 막기 위함.

    토큰은 이미 128비트 난수라 무차별 대입이 불가능하므로, 느린 KDF가 아니라
    sha256으로 충분하다(매 요청 검증하는 경로라 속도도 중요하다).
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_session(db: Session, user_id: uuid.UUID) -> str:
    """새 세션을 만들고 쿠키에 넣을 원문 토큰을 돌려준다."""
    from app.models.auth_session import AuthSession

    raw = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user_id,
            token_hash=_hash_token(raw),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.session_ttl_days),
        )
    )
    db.commit()
    return raw


def revoke_session(db: Session, raw_token: str) -> None:
    from app.models.auth_session import AuthSession

    row = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == _hash_token(raw_token))
    )
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()


def revoke_all_sessions(db: Session, user_id: uuid.UUID) -> int:
    """이 사용자의 유효한 세션을 전부 폐기한다(전 기기 로그아웃)."""
    from sqlalchemy import update

    from app.models.auth_session import AuthSession

    result = db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()
    return result.rowcount or 0


def purge_expired_sessions(db: Session) -> int:
    """만료·폐기된 세션 행을 정리한다.

    없어도 동작에는 문제가 없지만(검증 시 만료를 확인한다) 테이블이 무한정
    자란다. 월간 크롤 스케줄러가 도는 김에 같이 청소한다.
    """
    from sqlalchemy import delete, or_

    from app.models.auth_session import AuthSession

    from app.models.password_reset import PasswordResetToken

    now = datetime.now(timezone.utc)
    result = db.execute(
        delete(AuthSession).where(
            or_(
                AuthSession.expires_at < now,
                AuthSession.revoked_at.is_not(None),
            )
        )
    )
    db.execute(
        delete(PasswordResetToken).where(
            or_(
                PasswordResetToken.expires_at < now,
                PasswordResetToken.used_at.is_not(None),
            )
        )
    )
    db.commit()
    return result.rowcount or 0


# ---------------- 비밀번호 재설정 토큰 ----------------
def issue_reset_token(db: Session, user_id: uuid.UUID) -> str:
    """재설정 토큰 발급. 기존 미사용 토큰은 무효화한다.

    여러 개를 동시에 살려두면, 예전에 요청했다 잊은 링크가 계속 열려 있게 된다.
    """
    from sqlalchemy import update

    from app.models.password_reset import PasswordResetToken

    now = datetime.now(timezone.utc)
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user_id,
            token_hash=_hash_token(raw),
            expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes),
        )
    )
    db.commit()
    return raw


def consume_reset_token(db: Session, raw_token: str):
    """토큰을 검증하고 즉시 사용 처리한다. 유효하지 않으면 None.

    1회용이라 검증과 소모를 한 번에 한다. 분리하면 같은 링크를 두 번 쓸
    여지가 생긴다.
    """
    from app.models.password_reset import PasswordResetToken

    row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_token(raw_token)
        )
    )
    if row is None or row.used_at is not None:
        return None
    expires = _as_utc(row.expires_at)
    if expires and expires <= datetime.now(timezone.utc):
        return None

    row.used_at = datetime.now(timezone.utc)
    db.commit()
    return row


def invalidate_reset_tokens(db: Session, user_id: uuid.UUID) -> None:
    """미사용 재설정 토큰을 모두 무효화한다.

    비밀번호를 정상 경로로 바꾼 뒤에도 예전 재설정 링크가 살아 있으면,
    그 링크를 가진 사람이 다시 비밀번호를 바꿀 수 있다.
    """
    from sqlalchemy import update

    from app.models.password_reset import PasswordResetToken

    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(timezone.utc))
    )
    db.commit()


def _as_utc(dt: datetime | None) -> datetime | None:
    """SQLite는 tz를 버린다. 저장은 UTC이므로 naive는 UTC로 해석한다."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def set_session_cookie(response: Response, raw_token: str) -> None:
    """HttpOnly 쿠키로 심는다. JS가 읽을 수 없어야 XSS로 토큰이 새지 않는다."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )


def _lookup_user(db: Session, raw_token: str | None):
    """쿠키의 토큰으로 사용자를 찾는다. 무효면 None."""
    if not raw_token:
        return None
    from app.models.auth_session import AuthSession

    row = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == _hash_token(raw_token))
    )
    if row is None or row.revoked_at is not None:
        return None
    expires = _as_utc(row.expires_at)
    if expires and expires <= datetime.now(timezone.utc):
        return None
    return row.user


def optional_user(request: Request, db: Session = Depends(get_db)):
    """로그인했으면 User, 아니면 None. 지도처럼 비로그인도 허용하는 화면용."""
    return _lookup_user(db, request.cookies.get(settings.session_cookie_name))


def current_user(request: Request, db: Session = Depends(get_db)):
    """로그인 필수. 개인 데이터를 다루는 엔드포인트는 전부 이걸 쓴다.

    이전에는 user_id를 쿼리·바디로 받았는데, 그러면 UUID만 알면 남의
    신청서와 자기소개서를 그대로 읽을 수 있었다(IDOR).
    """
    user = _lookup_user(db, request.cookies.get(settings.session_cookie_name))
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "로그인이 필요합니다.",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return user


def rate_limit_auth(request: Request) -> None:
    """로그인·가입 시도 상한. 비밀번호 무차별 대입을 늦춘다."""
    limit = settings.auth_rate_limit_per_min
    if limit <= 0:
        return
    key = "auth:" + _client_key(request)
    now = time.monotonic()
    hits = _HITS[key]
    while hits and now - hits[0] > _WINDOW_SEC:
        hits.popleft()
    if len(hits) >= limit:
        retry_after = int(_WINDOW_SEC - (now - hits[0])) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"시도가 너무 잦습니다. {retry_after}초 후 다시 시도해 주세요.",
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now)
