"""챗봇 검증.

LLM 키가 없거나 DeepSeek가 죽어도 서비스는 살아야 한다. 여기 테스트는
전부 키 없는 상태(conftest가 비움)로 돌아 폴백 경로를 고정한다.
"""
from __future__ import annotations

from tests.conftest import make_scholarship


def test_chat_works_without_llm_key(client):
    """키가 없어도 500이 아니라 정상 응답이어야 한다."""
    r = client.post("/chat/message", json={"message": "장학금 찾아줘"})
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"]
    assert body["message"]


def test_session_is_kept_across_turns(client):
    first = client.post("/chat/message", json={"message": "안녕"}).json()
    sid = first["session_id"]

    second = client.post("/chat/message",
                         json={"session_id": sid, "message": "소득 3분위야"}).json()
    assert second["session_id"] == sid
    assert second["profile"].get("income_bracket") == 3


def test_conditions_are_parsed_from_free_text(client):
    sid = client.post("/chat/message", json={"message": "안녕"}).json()["session_id"]
    body = client.post("/chat/message",
                       json={"session_id": sid, "message": "학점 3.8이고 서울 살아"}).json()

    profile = body["profile"]
    assert profile.get("gpa") == 3.8
    assert profile.get("region") == "서울"


def test_no_candidates_when_db_is_empty(client):
    """공고가 없으면 지어내지 말고 빈 후보를 돌려줘야 한다(할루시네이션 방지)."""
    sid = client.post("/chat/message", json={"message": "안녕"}).json()["session_id"]
    body = client.post("/chat/message",
                       json={"session_id": sid, "message": "소득 3분위 학점 4.0 서울"}).json()
    assert body["candidates"] == []


def test_candidates_come_from_db(client, db):
    db.add(make_scholarship(content_key="c1", title="희망장학금",
                            eligibility={"income_bracket": [3]}))
    db.commit()

    sid = client.post("/chat/message", json={"message": "안녕"}).json()["session_id"]
    body = client.post("/chat/message",
                       json={"session_id": sid, "message": "소득 3분위야"}).json()

    titles = [c["title"] for c in body["candidates"]]
    assert "희망장학금" in titles


def test_new_condition_triggers_rematch_from_any_state(client, db):
    """어떤 상태에서든 새 조건을 말하면 즉시 재매칭돼야 한다(막다른 길 없음)."""
    db.add(make_scholarship(content_key="c2", title="저소득전용",
                            eligibility={"income_bracket": [0, 1]}))
    db.add(make_scholarship(content_key="c3", title="고소득가능",
                            eligibility={"income_bracket": [7, 8]}))
    db.commit()

    sid = client.post("/chat/message", json={"message": "안녕"}).json()["session_id"]

    low = client.post("/chat/message",
                      json={"session_id": sid, "message": "1분위야"}).json()
    assert [c["title"] for c in low["candidates"]] == ["저소득전용"]

    # 조건을 뒤집어도 막히지 않고 다시 매칭돼야 한다
    high = client.post("/chat/message",
                       json={"session_id": sid, "message": "아니 7분위야"}).json()
    assert [c["title"] for c in high["candidates"]] == ["고소득가능"]


def test_upload_rejects_unsupported_file_type(auth_client):
    r = auth_client.post("/chat/upload",
                    files={"file": ("bad.exe", b"MZ\x00binary", "application/octet-stream")})
    assert r.status_code == 415


def test_upload_rejects_oversized_file(auth_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_upload_mb", 1)
    big = b"x" * (2 * 1024 * 1024)
    r = auth_client.post("/chat/upload", files={"file": ("big.txt", big, "text/plain")})
    assert r.status_code == 413


def test_upload_requires_login(client):
    """첨부는 사용자 데이터로 저장되므로 로그인 없이는 막혀야 한다."""
    r = client.post("/chat/upload",
                    files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 401
