"""계정 설정 검증 — 프로필 저장, 비밀번호 변경, 전 기기 로그아웃, 탈퇴."""
from __future__ import annotations

import pytest

EMAIL = "student@khu.ac.kr"
PASSWORD = "correct-horse-8"
NEW_PASSWORD = "brand-new-pass-9"


def _signup(client, email=EMAIL, password=PASSWORD):
    client.cookies.clear()
    r = client.post("/auth/signup", json={"privacy_consent": True, "email": email, "password": password})
    assert r.status_code == 201
    return r.json()


# ---------------- 프로필 ----------------
def test_profile_is_persisted_to_account(client):
    """온보딩 설정이 계정에 남아야 기기를 바꿔도 유지된다."""
    _signup(client)
    r = client.put("/auth/profile", json={
        "gender": "female",
        "card_ids": [1, 2, 3],
        "telecom": "SKT",
        "preferred_pay_methods": ["kakao", "naver"],
        "student_credentials": ["student_tok"],
        "benefit_programs": ["onnuri"],
    })
    assert r.status_code == 200

    me = client.get("/auth/me").json()
    assert me["gender"] == "female"
    assert me["card_ids"] == [1, 2, 3]
    assert me["telecom"] == "SKT"
    assert me["preferred_pay_methods"] == ["kakao", "naver"]
    assert me["benefit_programs"] == ["onnuri"]


def test_partial_update_does_not_clear_other_fields(client):
    """온보딩과 챗봇이 서로 다른 필드를 쓴다. 한쪽이 다른 쪽을 지우면 안 된다."""
    _signup(client)
    client.put("/auth/profile", json={"card_ids": [7], "gender": "male"})
    client.put("/auth/profile", json={"income_bracket": 3})

    me = client.get("/auth/me").json()
    assert me["card_ids"] == [7], "챗봇 조건 저장이 온보딩 카드 설정을 지웠다"
    assert me["gender"] == "male"
    assert me["income_bracket"] == 3


def test_profile_survives_relogin(client):
    _signup(client)
    client.put("/auth/profile", json={"income_bracket": 5, "gpa": 3.8})

    client.cookies.clear()
    client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})

    me = client.get("/auth/me").json()
    assert me["income_bracket"] == 5
    assert me["gpa"] == 3.8


def test_profile_requires_login(client):
    assert client.put("/auth/profile", json={"gender": "male"}).status_code == 401


@pytest.mark.parametrize("payload", [
    {"income_bracket": 11},
    {"income_bracket": -1},
    {"gpa": 5.0},
])
def test_profile_rejects_out_of_range(client, payload):
    _signup(client)
    assert client.put("/auth/profile", json=payload).status_code == 422


# ---------------- 챗봇 조건 영속화 ----------------
def test_chat_conditions_are_saved_to_account(client):
    """대화 세션은 프로세스 메모리라 재시작하면 사라진다. 계정에 남아야 한다."""
    _signup(client)
    sid = client.post("/chat/message", json={"message": "안녕"}).json()["session_id"]
    client.post("/chat/message", json={"session_id": sid, "message": "소득 4분위이고 학점 3.7이야"})

    me = client.get("/auth/me").json()
    assert me["income_bracket"] == 4
    assert me["gpa"] == 3.7


def test_chat_restores_conditions_from_account(client):
    """서버가 재시작돼 대화 세션이 날아가도 조건을 다시 묻지 않아야 한다."""
    _signup(client)
    client.put("/auth/profile", json={"income_bracket": 2})

    # 새 대화(다른 session_id)를 시작해도 계정 조건이 실려야 한다
    body = client.post("/chat/message", json={"message": "장학금 알려줘"}).json()
    assert body["profile"].get("income_bracket") == 2


# ---------------- 비밀번호 변경 ----------------
def test_password_change_requires_current_password(client):
    _signup(client)
    r = client.put("/auth/password", json={
        "current_password": "wrong-password", "new_password": NEW_PASSWORD})
    assert r.status_code == 401


def test_password_change_switches_credentials(client):
    _signup(client)
    assert client.put("/auth/password", json={
        "current_password": PASSWORD, "new_password": NEW_PASSWORD}).status_code == 204

    client.cookies.clear()
    assert client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}).status_code == 200


def test_password_change_rejects_weak_new_password(client):
    _signup(client)
    r = client.put("/auth/password", json={
        "current_password": PASSWORD, "new_password": "short"})
    assert r.status_code == 422


def test_password_change_revokes_other_sessions(client):
    """비밀번호를 바꾸는 이유는 대개 '누가 보고 있을지도 모른다'이다.

    다른 기기 세션이 살아 있으면 바꾼 의미가 없다.
    """
    _signup(client)
    stolen = client.cookies.get("benefit_session")

    client.put("/auth/password", json={
        "current_password": PASSWORD, "new_password": NEW_PASSWORD})

    client.cookies.set("benefit_session", stolen)
    assert client.get("/auth/me").status_code == 401


def test_password_change_keeps_current_browser_logged_in(client):
    """바꾼 본인까지 로그아웃되면 불필요하게 번거롭다."""
    _signup(client)
    client.put("/auth/password", json={
        "current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert client.get("/auth/me").status_code == 200


# ---------------- 전 기기 로그아웃 ----------------
def test_logout_everywhere_revokes_all_sessions(client):
    _signup(client)
    first = client.cookies.get("benefit_session")

    # 같은 계정으로 다른 기기에서 로그인한 상황
    client.cookies.clear()
    client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert client.delete("/auth/sessions").status_code == 204

    client.cookies.set("benefit_session", first)
    assert client.get("/auth/me").status_code == 401


# ---------------- 탈퇴 ----------------
def test_delete_account_requires_password(client):
    _signup(client)
    assert client.post("/auth/delete", json={"password": "wrong-one"}).status_code == 401


def test_delete_account_removes_user_and_data(client, db):
    from app.models.application import ApplicationSource, UserApplication
    from app.models.user import User

    user = _signup(client)
    client.post("/applications", json={
        "scholarship_name": "내 신청서",
        "source": ApplicationSource.GENERATED.value,
        "documents": [{"content_text": "민감한 자기소개서"}],
    })
    client.post("/savings/spend", json={"original_amount": 10000, "final_amount": 9000})

    assert client.post("/auth/delete", json={"password": PASSWORD}).status_code == 204

    db.expire_all()
    assert db.get(User, __import__("uuid").UUID(user["id"])) is None
    assert db.query(UserApplication).count() == 0


def test_deleted_account_cannot_login(client):
    _signup(client)
    client.post("/auth/delete", json={"password": PASSWORD})

    client.cookies.clear()
    assert client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401


def test_email_is_reusable_after_deletion(client):
    """탈퇴했는데 같은 이메일로 재가입이 막히면 안 된다."""
    _signup(client)
    client.post("/auth/delete", json={"password": PASSWORD})

    client.cookies.clear()
    r = client.post("/auth/signup", json={"privacy_consent": True, "email": EMAIL, "password": PASSWORD})
    assert r.status_code == 201


# ---------------- 세션 정리 ----------------
def test_purge_removes_expired_and_revoked_sessions(client, db):
    from datetime import datetime, timedelta, timezone

    from app.core.security import purge_expired_sessions
    from app.models.auth_session import AuthSession

    _signup(client)
    row = db.query(AuthSession).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()

    assert purge_expired_sessions(db) == 1
    assert db.query(AuthSession).count() == 0


def test_purge_keeps_active_sessions(client, db):
    from app.core.security import purge_expired_sessions
    from app.models.auth_session import AuthSession

    _signup(client)
    assert purge_expired_sessions(db) == 0
    assert db.query(AuthSession).count() == 1


# ---------------- 레이트리밋 범위 ----------------
def test_rate_limit_does_not_lock_out_session_reads(client, monkeypatch):
    """/auth/me 는 앱을 열 때마다 호출된다. 무차별 대입 상한에 걸리면 안 된다."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "auth_rate_limit_per_min", 2)
    _signup(client)

    for _ in range(20):
        assert client.get("/auth/me").status_code == 200
    for _ in range(20):
        assert client.put("/auth/profile", json={"gpa": 3.5}).status_code == 200


def test_rate_limit_still_guards_login(client, monkeypatch):
    """비밀번호를 검사하는 곳은 계속 막혀야 한다."""
    from app.core.config import settings

    from app.core.security import _reset_rate_limit

    _signup(client)
    # 가입 호출이 이미 카운터에 남아 있으므로 초기화하고 로그인만 센다.
    _reset_rate_limit()
    monkeypatch.setattr(settings, "auth_rate_limit_per_min", 3)
    client.cookies.clear()

    codes = [
        client.post("/auth/login", json={"email": EMAIL, "password": "wrong-guess"}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401], codes
    assert 429 in codes[3:], codes
