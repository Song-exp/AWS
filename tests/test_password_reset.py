"""비밀번호 재설정 검증.

재설정은 '비밀번호 없이 비밀번호를 바꾸는' 경로다. 즉 인증을 우회하는
정식 통로이므로, 언제 통하고 언제 막히는지를 전부 고정해야 한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

EMAIL = "student@khu.ac.kr"
PASSWORD = "correct-horse-8"
NEW_PASSWORD = "brand-new-pass-9"


def _signup(client, email=EMAIL, password=PASSWORD):
    client.cookies.clear()
    r = client.post("/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201
    client.cookies.clear()


def _request_reset(client, db, email=EMAIL) -> str | None:
    """재설정을 요청하고, DB에서 발급된 토큰 원문 대신 행을 확인한다.

    토큰 원문은 메일에만 있고 DB에는 해시만 남는다. 테스트는 발송 함수를
    가로채 원문을 얻는다(아래 fixture 참고).
    """
    r = client.post("/auth/password/forgot", json={"email": email})
    assert r.status_code == 204
    return None


@pytest.fixture()
def sent_links(monkeypatch) -> list[str]:
    """메일로 나가는 재설정 링크를 가로챈다."""
    captured: list[str] = []

    def _fake(to, reset_url, ttl_minutes):
        captured.append(reset_url)

    from app.services import mailer

    monkeypatch.setattr(mailer, "send_password_reset", _fake)
    return captured


def _token_from(link: str) -> str:
    return link.split("reset_token=")[1]


# ---------------- 요청 ----------------
def test_forgot_sends_reset_link(client, sent_links):
    _signup(client)
    assert client.post("/auth/password/forgot", json={"email": EMAIL}).status_code == 204
    assert len(sent_links) == 1
    assert "reset_token=" in sent_links[0]


def test_forgot_does_not_leak_account_existence(client, sent_links):
    """가입 안 된 이메일에도 204를 준다. 아니면 계정 조회 API가 된다."""
    r = client.post("/auth/password/forgot", json={"email": "nobody@khu.ac.kr"})
    assert r.status_code == 204
    assert sent_links == [], "없는 계정에 메일을 보냈다"


def test_forgot_succeeds_even_if_mail_fails(client, monkeypatch):
    """발송 실패를 노출하면 그 자체로 계정 존재가 드러난다."""
    from app.services import mailer

    def _boom(**kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(mailer, "send_password_reset", _boom)
    _signup(client)
    assert client.post("/auth/password/forgot", json={"email": EMAIL}).status_code == 204


# ---------------- 재설정 ----------------
def test_reset_changes_password(client, sent_links):
    _signup(client)
    client.post("/auth/password/forgot", json={"email": EMAIL})
    token = _token_from(sent_links[0])

    assert client.post("/auth/password/reset", json={
        "token": token, "new_password": NEW_PASSWORD}).status_code == 204

    assert client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}).status_code == 200


def test_token_is_single_use(client, sent_links):
    """링크가 재사용되면 메일함을 본 사람이 계속 비밀번호를 바꿀 수 있다."""
    _signup(client)
    client.post("/auth/password/forgot", json={"email": EMAIL})
    token = _token_from(sent_links[0])

    assert client.post("/auth/password/reset", json={
        "token": token, "new_password": NEW_PASSWORD}).status_code == 204
    assert client.post("/auth/password/reset", json={
        "token": token, "new_password": "third-password-1"}).status_code == 400


def test_expired_token_is_rejected(client, db, sent_links):
    from app.models.password_reset import PasswordResetToken

    _signup(client)
    client.post("/auth/password/forgot", json={"email": EMAIL})
    token = _token_from(sent_links[0])

    row = db.query(PasswordResetToken).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    assert client.post("/auth/password/reset", json={
        "token": token, "new_password": NEW_PASSWORD}).status_code == 400


def test_forged_token_is_rejected(client):
    assert client.post("/auth/password/reset", json={
        "token": "made-up-token", "new_password": NEW_PASSWORD}).status_code == 400


def test_requesting_again_invalidates_previous_link(client, sent_links):
    """예전에 요청했다 잊은 링크가 계속 열려 있으면 안 된다."""
    _signup(client)
    client.post("/auth/password/forgot", json={"email": EMAIL})
    client.post("/auth/password/forgot", json={"email": EMAIL})
    old, new = _token_from(sent_links[0]), _token_from(sent_links[1])

    assert client.post("/auth/password/reset", json={
        "token": old, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post("/auth/password/reset", json={
        "token": new, "new_password": NEW_PASSWORD}).status_code == 204


@pytest.mark.parametrize("password", ["", "short", "1234567"])
def test_reset_rejects_weak_password(client, sent_links, password):
    _signup(client)
    client.post("/auth/password/forgot", json={"email": EMAIL})
    token = _token_from(sent_links[0])
    assert client.post("/auth/password/reset", json={
        "token": token, "new_password": password}).status_code == 422


def test_reset_revokes_existing_sessions(client, sent_links):
    """비밀번호를 잃어버렸다면 계정이 남의 손에 있었을 수 있다."""
    client.cookies.clear()
    client.post("/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    stolen = client.cookies.get("benefit_session")

    client.post("/auth/password/forgot", json={"email": EMAIL})
    token = _token_from(sent_links[0])
    client.post("/auth/password/reset", json={
        "token": token, "new_password": NEW_PASSWORD})

    client.cookies.set("benefit_session", stolen)
    assert client.get("/auth/me").status_code == 401


def test_normal_password_change_invalidates_reset_links(client, sent_links):
    """재설정 링크를 요청해 둔 채 정상 변경했다면, 그 링크는 죽어야 한다."""
    client.cookies.clear()
    client.post("/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    client.post("/auth/password/forgot", json={"email": EMAIL})
    token = _token_from(sent_links[0])

    client.put("/auth/password", json={
        "current_password": PASSWORD, "new_password": NEW_PASSWORD})

    assert client.post("/auth/password/reset", json={
        "token": token, "new_password": "attacker-pass-1"}).status_code == 400


def test_token_is_not_stored_raw(client, db, sent_links):
    from app.models.password_reset import PasswordResetToken

    _signup(client)
    client.post("/auth/password/forgot", json={"email": EMAIL})
    token = _token_from(sent_links[0])

    row = db.query(PasswordResetToken).one()
    assert row.token_hash != token
    assert len(row.token_hash) == 64


def test_reset_is_rate_limited(client, monkeypatch):
    """토큰 추측을 무제한으로 시도하게 두면 안 된다."""
    from app.core.config import settings
    from app.core.security import _reset_rate_limit

    _reset_rate_limit()
    monkeypatch.setattr(settings, "auth_rate_limit_per_min", 3)
    codes = [
        client.post("/auth/password/reset", json={
            "token": f"guess-{i}", "new_password": NEW_PASSWORD}).status_code
        for i in range(5)
    ]
    assert codes[:3] == [400, 400, 400], codes
    assert 429 in codes[3:], codes


def test_purge_removes_used_and_expired_tokens(client, db, sent_links):
    from app.core.security import purge_expired_sessions
    from app.models.password_reset import PasswordResetToken

    _signup(client)
    client.post("/auth/password/forgot", json={"email": EMAIL})
    token = _token_from(sent_links[0])
    client.post("/auth/password/reset", json={
        "token": token, "new_password": NEW_PASSWORD})

    purge_expired_sessions(db)
    assert db.query(PasswordResetToken).count() == 0
