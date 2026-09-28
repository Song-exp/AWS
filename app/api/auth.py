"""회원가입 · 로그인 · 로그아웃.

세션은 HttpOnly 쿠키로 오간다. 프론트가 토큰을 JS로 들고 있지 않으므로
XSS가 나도 세션이 통째로 새지 않는다.

기존 익명 사용자 승계: 로그인 없는 MVP 시절 프론트는 localStorage에
직접 만든 UUID로 자기소개서·신청서를 쌓았다. 가입할 때 그 UUID를 함께
보내면 해당 데이터를 새 계정으로 옮긴다.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    MAX_PASSWORD_LENGTH,
    UNSUBSCRIBE_PURPOSE,
    VERIFY_PURPOSE,
    read_link_token,
    sign_link_token,
    consume_reset_token,
    invalidate_reset_tokens,
    issue_reset_token,
    revoke_all_sessions,
    MIN_PASSWORD_LENGTH,
    clear_session_cookie,
    current_user,
    hash_password,
    is_valid_email,
    issue_session,
    normalize_email,
    rate_limit_auth,
    revoke_session,
    set_session_cookie,
    verify_password,
)
from app.core.config import settings
from app.models.application import UserApplication
from app.models.saving import SavingRecord
from app.models.user import User
from app.services import mailer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# 무차별 대입 상한은 **비밀번호를 검사하는** 엔드포인트에만 건다.
# /auth/me 는 앱을 열 때마다 호출되고 /auth/profile 은 온보딩에서 여러 번
# 불린다. 여기까지 상한에 넣으면 정상 사용자가 자기 세션 조회에서 잠긴다.
_BRUTE_FORCE_GUARD = [Depends(rate_limit_auth)]


class SignupIn(BaseModel):
    email: str
    password: str
    nickname: str | None = None
    # 로그인 전에 이 브라우저가 쓰던 익명 UUID. 있으면 데이터를 승계한다.
    claim_user_id: uuid.UUID | None = None
    # 개인정보 수집·이용 동의(필수). 기본값이 False라 빠뜨리면 가입이 거절된다.
    privacy_consent: bool = False
    # 마감 알림 메일 수신 동의(선택).
    reminder_opt_in: bool = False


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str | None = None
    email_verified: bool = False
    reminder_enabled: bool = False
    nickname: str | None = None
    income_bracket: int | None = None
    gpa: float | None = None
    grade_level: str | None = None
    region: str | None = None
    major: str | None = None
    interests: list[str] = Field(default_factory=list)
    preferred_pay_methods: list[str] = Field(default_factory=list)
    gender: str | None = None
    telecom: str | None = None
    card_ids: list[int] = Field(default_factory=list)
    student_credentials: list[str] = Field(default_factory=list)
    benefit_programs: list[str] = Field(default_factory=list)


def _to_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        email=u.email,
        email_verified=u.email_verified_at is not None,
        reminder_enabled=bool(u.reminder_enabled),
        nickname=u.nickname,
        income_bracket=u.income_bracket,
        gpa=u.gpa,
        grade_level=u.grade_level,
        region=u.region,
        major=u.major,
        interests=list(u.interests or []),
        preferred_pay_methods=list(u.preferred_pay_methods or []),
        gender=u.gender,
        telecom=u.telecom,
        card_ids=list(u.card_ids or []),
        student_credentials=list(u.student_credentials or []),
        benefit_programs=list(u.benefit_programs or []),
    )


def _validate_credentials(email: str, password: str) -> str:
    """형식 검증. 통과하면 정규화된 이메일을 돌려준다."""
    normalized = normalize_email(email)
    if not is_valid_email(normalized):
        raise HTTPException(422, "이메일 형식이 올바르지 않습니다.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            422, f"비밀번호는 최소 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다."
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise HTTPException(
            422, f"비밀번호는 {MAX_PASSWORD_LENGTH}자를 넘을 수 없습니다."
        )
    return normalized


def _claim_anonymous_data(db: Session, claim_id: uuid.UUID, new_id: uuid.UUID) -> int:
    """익명 시절 데이터를 새 계정으로 옮긴다.

    ponytail: 소유 증명이 'UUID를 알고 있다'뿐이다. 원래도 그 UUID를 알면
    데이터를 읽을 수 있었으므로 노출 범위가 넓어지지는 않지만, 가져가기는
    선착순이다. 그래서 **계정에 연결된 적 없는 UUID만** 승계를 허용한다.
    로그인 이전 데이터를 위한 일회성 경로이므로, 기존 사용자 이전이 끝나면
    제거하는 것이 맞다.
    """
    if claim_id == new_id:
        return 0
    owner = db.get(User, claim_id)
    if owner is not None and owner.password_hash is not None:
        # 이미 계정이 붙은 UUID는 남의 것이다.
        raise HTTPException(409, "이미 계정에 연결된 데이터입니다.")

    moved = 0
    for model in (UserApplication, SavingRecord):
        result = db.execute(
            update(model).where(model.user_id == claim_id).values(user_id=new_id)
        )
        moved += result.rowcount or 0
    db.commit()
    return moved


def _send_verification(user: User) -> None:
    """인증 메일 발송. 실패해도 가입은 막지 않는다(마이페이지에서 다시 보낼 수 있다)."""
    token = sign_link_token(
        VERIFY_PURPOSE,
        user.id,
        user.email,
        ttl=timedelta(hours=settings.email_verify_ttl_hours),
    )
    try:
        mailer.send_email_verification(
            to=user.email,
            verify_url=f"{settings.app_base_url.rstrip('/')}/?verify_token={token}",
            ttl_hours=settings.email_verify_ttl_hours,
        )
    except Exception:  # noqa: BLE001
        logger.exception("이메일 인증 메일 발송 실패: %s", user.email)


@router.post("/signup", response_model=UserOut, status_code=201, dependencies=_BRUTE_FORCE_GUARD)
def signup(payload: SignupIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    email = _validate_credentials(payload.email, payload.password)
    if not payload.privacy_consent:
        raise HTTPException(422, "개인정보 수집·이용에 동의해야 가입할 수 있습니다.")

    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "이미 가입된 이메일입니다.")

    user = User(
        email=email,
        nickname=payload.nickname,
        password_hash=hash_password(payload.password),
        privacy_consent_at=datetime.now(timezone.utc),
        reminder_enabled=payload.reminder_opt_in,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _send_verification(user)

    if payload.claim_user_id:
        _claim_anonymous_data(db, payload.claim_user_id, user.id)

    set_session_cookie(response, issue_session(db, user.id))
    return _to_out(user)


@router.post("/login", response_model=UserOut, dependencies=_BRUTE_FORCE_GUARD)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    email = normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))

    # 이메일이 없을 때와 비밀번호가 틀렸을 때의 응답을 구분하지 않는다.
    # 구분하면 가입 여부를 알아내는 계정 열거가 가능해진다.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다.")

    set_session_cookie(response, issue_session(db, user.id))
    return _to_out(user)


@router.post("/logout", status_code=204, response_class=Response)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    """세션을 서버에서 폐기하고 쿠키를 지운다.

    쿠키만 지우면 토큰은 그대로 유효하다. 공용 PC에서 쿠키를 미리 복사해 둔
    경우 로그아웃 후에도 계정에 접근할 수 있으므로 반드시 서버에서 폐기한다.
    """
    raw = request.cookies.get(settings.session_cookie_name)
    if raw:
        revoke_session(db, raw)
    out = Response(status_code=204)
    clear_session_cookie(out)
    return out


@router.get("/me", response_model=UserOut)
def whoami(user: User = Depends(current_user)) -> UserOut:
    """현재 로그인한 사용자. 프론트가 새로고침 후 세션 복원에 쓴다."""
    return _to_out(user)


# ---------------- 프로필 ----------------
class ProfileIn(BaseModel):
    """프로필 수정. 보낸 필드만 바꾸고, 안 보낸 필드는 그대로 둔다.

    None 과 '보내지 않음'을 구분해야 한다. 온보딩은 일부만 보내고 챗봇은
    다른 일부만 보내는데, 미지정을 None 으로 처리하면 서로의 값을 지운다.
    """

    nickname: str | None = None
    income_bracket: int | None = Field(default=None, ge=0, le=10)
    gpa: float | None = Field(default=None, ge=0.0, le=4.5)
    grade_level: str | None = None
    region: str | None = None
    major: str | None = None
    interests: list[str] | None = None
    preferred_pay_methods: list[str] | None = None
    gender: str | None = None
    telecom: str | None = None
    card_ids: list[int] | None = None
    student_credentials: list[str] | None = None
    benefit_programs: list[str] | None = None
    # 마감 알림 메일 수신 여부. 마이페이지에서 켜고 끈다.
    reminder_enabled: bool | None = None


@router.put("/profile", response_model=UserOut)
def update_profile(
    payload: ProfileIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """온보딩·마이페이지에서 프로필을 저장한다.

    localStorage 에만 있던 설정을 계정에 붙여 기기를 바꿔도 유지되게 한다.
    """
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return _to_out(user)


# ---------------- 계정 관리 ----------------
class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


@router.put("/password", status_code=204, response_class=Response, dependencies=_BRUTE_FORCE_GUARD)
def change_password(
    payload: PasswordChangeIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """비밀번호 변경. 현재 비밀번호를 반드시 확인한다.

    확인 없이 바꾸게 하면, 남의 로그인된 화면을 잠깐 만진 사람이 비밀번호를
    바꿔 계정을 통째로 가져갈 수 있다.
    """
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(401, "현재 비밀번호가 올바르지 않습니다.")
    if len(payload.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            422, f"비밀번호는 최소 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다."
        )
    if len(payload.new_password) > MAX_PASSWORD_LENGTH:
        raise HTTPException(
            422, f"비밀번호는 {MAX_PASSWORD_LENGTH}자를 넘을 수 없습니다."
        )

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    # 예전에 요청한 재설정 링크가 살아 있으면 그 링크로 다시 바꿀 수 있다.
    invalidate_reset_tokens(db, user.id)

    # 비밀번호를 바꾸는 이유는 대개 '누가 보고 있을지도 모른다'이다.
    # 다른 기기의 세션을 살려두면 바꾼 의미가 없으므로 전부 끊고,
    # 지금 쓰는 이 브라우저만 새 세션으로 이어준다.
    revoke_all_sessions(db, user.id)
    out = Response(status_code=204)
    set_session_cookie(out, issue_session(db, user.id))
    return out


@router.delete("/sessions", status_code=204, response_class=Response)
def logout_everywhere(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    """모든 기기에서 로그아웃. 계정이 털렸다고 의심될 때 쓴다."""
    revoke_all_sessions(db, user.id)
    out = Response(status_code=204)
    clear_session_cookie(out)
    return out


class DeleteAccountIn(BaseModel):
    password: str


@router.post("/delete", status_code=204, response_class=Response, dependencies=_BRUTE_FORCE_GUARD)
def delete_account(
    payload: DeleteAccountIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """회원 탈퇴. 계정과 개인 데이터를 실제로 지운다.

    과거 신청서에는 주민번호·학번·성적이 섞여 있을 수 있어 보관 자체가
    위험이다. 탈퇴 요청은 소프트 삭제로 남기지 않고 실제로 삭제한다.
    업로드된 원본 파일도 함께 지운다(DB만 지우면 파일이 디스크에 남는다).
    """
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "비밀번호가 올바르지 않습니다.")

    rows = db.scalars(
        select(UserApplication).where(UserApplication.user_id == user.id)
    ).all()
    for row in rows:
        if row.source_file_path and os.path.exists(row.source_file_path):
            try:
                os.remove(row.source_file_path)
            except OSError:
                # 파일 삭제 실패가 계정 삭제를 막지는 않게 한다.
                logger.warning("업로드 파일 삭제 실패: %s", row.source_file_path)
        db.delete(row)

    db.execute(delete(SavingRecord).where(SavingRecord.user_id == user.id))
    revoke_all_sessions(db, user.id)
    db.delete(user)
    db.commit()

    out = Response(status_code=204)
    clear_session_cookie(out)
    return out


# ---------------- 비밀번호 재설정(분실) ----------------
class ForgotPasswordIn(BaseModel):
    email: str


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str


@router.post(
    "/password/forgot",
    status_code=204,
    response_class=Response,
    dependencies=_BRUTE_FORCE_GUARD,
)
def forgot_password(
    payload: ForgotPasswordIn, db: Session = Depends(get_db)
) -> Response:
    """재설정 링크를 메일로 보낸다.

    가입 여부와 무관하게 항상 204다. 응답이 갈리면 이 엔드포인트가 '이 이메일이
    가입돼 있는가'를 알려주는 조회 API가 되어버린다.

    메일 발송 실패도 204로 삼킨다. 실패를 노출하면 같은 방식으로 계정 존재가
    드러나기 때문이다(없는 계정은 애초에 발송을 시도하지 않으므로 실패하지 않는다).
    """
    email = normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))

    if user is not None:
        raw = issue_reset_token(db, user.id)
        reset_url = f"{settings.app_base_url.rstrip('/')}/?reset_token={raw}"
        try:
            mailer.send_password_reset(
                to=email,
                reset_url=reset_url,
                ttl_minutes=settings.password_reset_ttl_minutes,
            )
        except Exception:  # noqa: BLE001
            logger.exception("비밀번호 재설정 메일 발송 실패: %s", email)

    return Response(status_code=204)


@router.post(
    "/password/reset",
    status_code=204,
    response_class=Response,
    dependencies=_BRUTE_FORCE_GUARD,
)
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)) -> Response:
    """토큰으로 새 비밀번호를 설정한다. 토큰은 1회용이다."""
    if len(payload.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            422, f"비밀번호는 최소 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다."
        )
    if len(payload.new_password) > MAX_PASSWORD_LENGTH:
        raise HTTPException(
            422, f"비밀번호는 {MAX_PASSWORD_LENGTH}자를 넘을 수 없습니다."
        )

    row = consume_reset_token(db, payload.token)
    if row is None:
        raise HTTPException(400, "만료되었거나 이미 사용된 링크입니다.")

    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(400, "만료되었거나 이미 사용된 링크입니다.")

    user.password_hash = hash_password(payload.new_password)
    # 재설정 링크는 그 주소의 메일함에서만 열 수 있다. 소유 확인으로 친다.
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
    db.commit()

    # 비밀번호를 잃어버렸다는 것은 계정이 남의 손에 있었을 수 있다는 뜻이다.
    # 기존 세션을 전부 끊는다. 재설정 후에는 새로 로그인하게 한다.
    revoke_all_sessions(db, user.id)
    return Response(status_code=204)


# ---------------- 이메일 인증 · 알림 수신 거부 ----------------
class LinkTokenIn(BaseModel):
    token: str


def _user_for_link(db: Session, purpose: str, token: str) -> User:
    """메일 링크의 토큰으로 사용자를 찾는다. 주소가 바뀌었으면 옛 링크는 무효다."""
    parsed = read_link_token(purpose, token)
    user = db.get(User, parsed[0]) if parsed else None
    if user is None or user.email != parsed[1]:
        raise HTTPException(400, "만료되었거나 올바르지 않은 링크입니다.")
    return user


@router.post(
    "/email/verify",
    status_code=204,
    response_class=Response,
    dependencies=_BRUTE_FORCE_GUARD,
)
def verify_email(payload: LinkTokenIn, db: Session = Depends(get_db)) -> Response:
    """인증 메일의 링크 처리. 여러 번 눌러도 결과가 같다."""
    user = _user_for_link(db, VERIFY_PURPOSE, payload.token)
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        db.commit()
    return Response(status_code=204)


@router.post(
    "/email/resend",
    status_code=204,
    response_class=Response,
    dependencies=_BRUTE_FORCE_GUARD,
)
def resend_verification(user: User = Depends(current_user)) -> Response:
    """인증 메일 다시 보내기. 분당 상한이 걸려 있어 메일 폭탄으로 쓸 수 없다."""
    if user.email_verified_at is None and user.email:
        _send_verification(user)
    return Response(status_code=204)


@router.post(
    "/reminders/unsubscribe",
    status_code=204,
    response_class=Response,
    dependencies=_BRUTE_FORCE_GUARD,
)
def unsubscribe_reminders(
    payload: LinkTokenIn, db: Session = Depends(get_db)
) -> Response:
    """알림 메일의 수신 거부 링크 처리. 로그인 없이 동작해야 한다."""
    user = _user_for_link(db, UNSUBSCRIBE_PURPOSE, payload.token)
    if user.reminder_enabled:
        user.reminder_enabled = False
        db.commit()
    return Response(status_code=204)
