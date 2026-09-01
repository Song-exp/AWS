"""인가(authorization) 검증 — 남의 데이터에 접근할 수 없어야 한다.

로그인을 붙인 이유가 이것이다. 전에는 user_id를 쿼리·바디로 받아서
UUID만 알면 남의 자기소개서를 읽고 신청서를 지울 수 있었다.
"""
from __future__ import annotations

import pytest

A = ("alice@khu.ac.kr", "alice-password-1")
B = ("bob@khu.ac.kr", "bob-password-1")


def _signup(client, creds):
    client.cookies.clear()
    r = client.post("/auth/signup", json={"email": creds[0], "password": creds[1]})
    assert r.status_code == 201
    return r.json()["id"]


def _login(client, creds):
    client.cookies.clear()
    r = client.post("/auth/login", json={"email": creds[0], "password": creds[1]})
    assert r.status_code == 200


# ---------------- 비로그인 차단 ----------------
@pytest.mark.parametrize("method,path,kwargs", [
    ("get", "/me/summary", {}),
    ("get", "/applications", {}),
    ("post", "/applications", {"json": {"scholarship_name": "x", "documents": []}}),
    ("post", "/ai/draft", {"json": {"scholarship_id": 1, "questions": ["q"]}}),
    ("get", "/savings/summary", {}),
    ("post", "/savings/spend", {"json": {"original_amount": 1000, "final_amount": 0}}),
    ("post", "/savings/view", {"json": {}}),
])
def test_personal_endpoints_reject_anonymous(client, method, path, kwargs):
    r = getattr(client, method)(path, **kwargs)
    assert r.status_code == 401, f"{path} 가 비로그인으로 {r.status_code} 를 반환했다"


def test_public_endpoints_still_work_without_login(client, seed_stores):
    """지도·옵션은 로그인 없이도 보여야 한다. 진입장벽을 높이면 안 된다."""
    assert client.get("/stores/nearby", params={"lat": 37.5966, "lng": 127.0525}).status_code == 200
    assert client.get("/meta/options").status_code == 200
    assert client.post("/chat/message", json={"message": "안녕"}).status_code == 200


# ---------------- 데이터 격리 ----------------
def test_user_cannot_read_others_applications(client):
    _signup(client, A)
    client.post("/applications", json={
        "scholarship_name": "앨리스 장학금",
        "documents": [{"content_text": "앨리스의 자기소개서"}],
    })

    _signup(client, B)
    rows = client.get("/applications").json()
    assert rows == [], "밥이 앨리스의 신청서를 봤다"

    summary = client.get("/me/summary").json()
    assert summary["applications"] == []
    assert summary["documents"] == []


def test_user_cannot_delete_others_application(client):
    _signup(client, A)
    app_id = client.post("/applications", json={
        "scholarship_name": "앨리스 장학금", "documents": [],
    }).json()["id"]

    _signup(client, B)
    assert client.delete(f"/applications/{app_id}").status_code == 404

    # 앨리스 것은 그대로 남아 있어야 한다
    _login(client, A)
    assert len(client.get("/applications").json()) == 1


def test_user_can_delete_own_application(client):
    _signup(client, A)
    app_id = client.post("/applications", json={
        "scholarship_name": "내 장학금", "documents": [],
    }).json()["id"]

    assert client.delete(f"/applications/{app_id}").status_code == 204
    assert client.get("/applications").json() == []


def test_savings_are_isolated_per_account(client):
    _signup(client, A)
    client.post("/savings/spend", json={"original_amount": 50000, "final_amount": 0})

    _signup(client, B)
    s = client.get("/savings/summary").json()
    assert s["month_saved"] == 0, "밥의 대시보드에 앨리스의 절감액이 섞였다"


def test_summary_uses_session_not_supplied_user_id(client):
    """쿼리로 남의 user_id를 넣어도 무시돼야 한다."""
    alice_id = _signup(client, A)
    client.post("/savings/spend", json={"original_amount": 50000, "final_amount": 0})

    _signup(client, B)
    s = client.get("/savings/summary", params={"user_id": alice_id}).json()
    assert s["user_id"] != alice_id
    assert s["month_saved"] == 0


# ---------------- 익명 데이터 승계 ----------------
def test_signup_claims_anonymous_data(client, db):
    """로그인 도입 전 localStorage UUID로 쌓인 데이터를 계정으로 옮긴다."""
    import uuid as _uuid

    from app.models.application import ApplicationSource, UserApplication

    anon = _uuid.uuid4()
    db.add(UserApplication(
        user_id=anon,
        scholarship_name="익명 시절 신청서",
        source=ApplicationSource.UPLOADED,
    ))
    db.commit()

    client.cookies.clear()
    r = client.post("/auth/signup", json={
        "email": A[0], "password": A[1], "claim_user_id": str(anon),
    })
    assert r.status_code == 201

    rows = client.get("/applications").json()
    assert [x["scholarship_name"] for x in rows] == ["익명 시절 신청서"]


def test_cannot_claim_data_already_owned_by_an_account(client, db):
    """이미 계정이 붙은 UUID는 가로챌 수 없어야 한다."""
    alice_id = _signup(client, A)

    client.cookies.clear()
    r = client.post("/auth/signup", json={
        "email": B[0], "password": B[1], "claim_user_id": alice_id,
    })
    assert r.status_code == 409
