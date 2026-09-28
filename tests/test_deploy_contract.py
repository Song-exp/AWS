"""배포 규약 검증.

여기 있는 테스트가 깨지면 '배포하면 안 되는 상태'라는 뜻이다.
"""
from __future__ import annotations

import pytest

from tests.conftest import ADMIN_TOKEN


# ---------------- 헬스체크 규약 ----------------
def test_health_is_liveness_only(client):
    """liveness 는 의존성을 보지 않는다(로드밸런서가 때리는 경로)."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_reports_dependencies(client):
    """readiness 는 DB를 실제로 확인하고 LLM 가용 여부를 알린다."""
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] is True
    assert body["llm"] is False  # conftest가 키를 비웠다


def test_ready_returns_503_when_db_down(client, monkeypatch):
    """DB가 죽으면 200이 아니라 503이어야 트래픽이 끊긴다."""
    import app.core.db as core_db

    class _BrokenEngine:
        def connect(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(core_db, "engine", _BrokenEngine())
    r = client.get("/ready")
    assert r.status_code == 503


# ---------------- 관리자 인증 규약 ----------------
@pytest.mark.parametrize("method,path", [
    ("get", "/admin/crawl/runs"),
    ("post", "/admin/crawl/run"),
    ("post", "/admin/index/run"),
])
def test_admin_endpoints_reject_anonymous(client, method, path):
    """크롤·재색인 트리거는 인증 없이 열려 있으면 안 된다."""
    r = getattr(client, method)(path)
    assert r.status_code == 401, f"{path} 가 인증 없이 {r.status_code} 를 반환했다"


def test_admin_endpoint_accepts_valid_token(client):
    r = client.get("/admin/crawl/runs", headers={"X-Admin-Token": ADMIN_TOKEN})
    assert r.status_code == 200
    assert r.json() == []


def test_admin_endpoint_rejects_wrong_token(client):
    r = client.get("/admin/crawl/runs", headers={"X-Admin-Token": "wrong"})
    assert r.status_code == 401


# ---------------- 레이트리밋 규약(LLM 비용 방어) ----------------
def test_chat_is_rate_limited(client, monkeypatch):
    """상한을 넘으면 429. 없으면 익명 사용자가 LLM 비용을 무제한으로 태운다."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "chat_rate_limit_per_min", 3)

    codes = [
        client.post("/chat/message", json={"message": "안녕"}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [200, 200, 200], codes
    assert codes[3:] == [429, 429], codes


def test_rate_limit_response_has_retry_after(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "chat_rate_limit_per_min", 1)
    client.post("/chat/message", json={"message": "안녕"})
    r = client.post("/chat/message", json={"message": "안녕"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


# ---------------- 설정 규약 ----------------
def test_production_boot_fails_without_required_settings():
    """운영 필수값이 없으면 조용히 폴백하지 말고 부팅에 실패해야 한다."""
    from app.core.config import Settings, _require_production_settings

    s = Settings(
        app_env="production",
        deepseek_api_key="",
        admin_token="",
        secret_key="dev-insecure-secret",
        database_url="sqlite:///./data/app.db",
        cors_origins="http://localhost:5173",
        smtp_host="",
        app_base_url="http://localhost:5173",
    )
    with pytest.raises(RuntimeError) as e:
        _require_production_settings(s)

    msg = str(e.value)
    for expected in ["DEEPSEEK_API_KEY", "ADMIN_TOKEN", "SECRET_KEY", "DATABASE_URL",
                     "CORS_ORIGINS", "SESSION_COOKIE_SECURE",
                     "SMTP_HOST", "APP_BASE_URL"]:
        assert expected in msg, f"{expected} 누락을 잡지 못했다: {msg}"


def test_production_boot_passes_when_configured():
    from app.core.config import Settings, _require_production_settings

    s = Settings(
        app_env="production",
        deepseek_api_key="sk-real",
        admin_token="strong-token",
        secret_key="k" * 32,
        database_url="postgresql+psycopg://u:p@db:5432/app",
        cors_origins="https://benefit.example.com",
        session_cookie_secure=True,
        smtp_host="smtp.example.com",
        app_base_url="https://benefit.example.com",
    )
    _require_production_settings(s)  # 예외가 없어야 한다


def test_cors_origins_parsed_as_list():
    from app.core.config import Settings

    s = Settings(cors_origins="https://a.com, https://b.com ,")
    assert s.cors_origin_list == ["https://a.com", "https://b.com"]
