"""로그인 인증 검증.

인증 테스트의 핵심은 '되는 것'이 아니라 '막히는 것'이다. 로그인 성공만
확인하면, 비로그인 접근이 열려 있어도 전부 초록으로 통과한다.
"""
from __future__ import annotations

import uuid

import pytest

EMAIL = "student@khu.ac.kr"
PASSWORD = "correct-horse-8"


def signup(client, email=EMAIL, password=PASSWORD, **kw):
    return client.post("/auth/signup", json={"email": email, "password": password, **kw})


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


# ---------------- 가입 ----------------
def test_signup_creates_account_and_session(client):
    r = signup(client)
    assert r.status_code == 201
    assert r.json()["email"] == EMAIL
    assert client.cookies.get("benefit_session")


def test_signup_rejects_duplicate_email(client):
    signup(client)
    client.cookies.clear()
    assert signup(client).status_code == 409


def test_signup_email_is_case_insensitive(client):
    """대소문자만 바꿔 같은 이메일로 두 계정이 생기면 안 된다."""
    signup(client, email="Student@KHU.ac.kr")
    client.cookies.clear()
    assert signup(client, email="student@khu.ac.kr").status_code == 409


@pytest.mark.parametrize("email", ["nope", "a@@b.com", "a b@c.com", "@b.com", "a@b"])
def test_signup_rejects_malformed_email(client, email):
    assert signup(client, email=email).status_code == 422


@pytest.mark.parametrize("password", ["", "short", "1234567"])
def test_signup_rejects_weak_password(client, password):
    assert signup(client, password=password).status_code == 422


def test_signup_rejects_absurdly_long_password(client):
    """길이 제한이 없으면 긴 입력으로 scrypt CPU를 태울 수 있다."""
    assert signup(client, password="x" * 5000).status_code == 422


# ---------------- 로그인 ----------------
def test_login_succeeds_with_correct_password(client):
    signup(client)
    client.cookies.clear()
    r = login(client)
    assert r.status_code == 200
    assert client.cookies.get("benefit_session")


def test_login_rejects_wrong_password(client):
    signup(client)
    client.cookies.clear()
    assert login(client, password="wrong-password-1").status_code == 401


def test_login_does_not_leak_account_existence(client):
    """'없는 이메일'과 '틀린 비밀번호'의 응답이 같아야 가입 여부를 못 캔다."""
    signup(client)
    client.cookies.clear()

    unknown = login(client, email="nobody@khu.ac.kr", password=PASSWORD)
    wrong = login(client, password="wrong-password-1")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_password_is_not_stored_in_plaintext(client, db):
    from app.models.user import User

    signup(client)
    user = db.query(User).filter(User.email == EMAIL).one()
    assert PASSWORD not in (user.password_hash or "")
    assert user.password_hash.startswith("scrypt$")


# ---------------- 세션 ----------------
def test_me_returns_current_user(client):
    signup(client)
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


def test_me_requires_login(client):
    assert client.get("/auth/me").status_code == 401


def test_logout_revokes_session_on_server(client):
    """쿠키만 지우면 토큰은 그대로 유효하다. 서버에서 폐기돼야 한다."""
    signup(client)
    token = client.cookies.get("benefit_session")

    client.post("/auth/logout")

    # 로그아웃 전에 복사해 둔 쿠키를 그대로 다시 제시한다.
    client.cookies.set("benefit_session", token)
    assert client.get("/auth/me").status_code == 401


def test_forged_session_token_is_rejected(client):
    client.cookies.set("benefit_session", "not-a-real-token")
    assert client.get("/auth/me").status_code == 401


def test_expired_session_is_rejected(client, db):
    from datetime import datetime, timedelta, timezone

    from app.models.auth_session import AuthSession

    signup(client)
    row = db.query(AuthSession).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    assert client.get("/auth/me").status_code == 401


def test_session_cookie_is_httponly(client):
    """JS가 읽을 수 있으면 XSS 한 번에 세션이 통째로 샌다."""
    r = signup(client)
    cookie_header = r.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header


def test_session_token_is_not_stored_raw(client, db):
    """DB가 유출돼도 세션을 재사용하지 못해야 한다."""
    from app.models.auth_session import AuthSession

    signup(client)
    token = client.cookies.get("benefit_session")
    row = db.query(AuthSession).one()
    assert row.token_hash != token
    assert len(row.token_hash) == 64
