"""FastAPI 앱 진입점.

실행: uvicorn app.main:app --reload

통합 서비스:
  - 페이픽(지도): 주변 편의점 간편결제 할인 (/stores)
  - 장학금 챗봇: 매칭·초안·아카이빙 (/chat, /scholarships, /ai, /applications)
일간 크롤 스케줄러(매일 00:10 KST)를 lifespan에서 start/stop 한다.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    ai,
    applications,
    auth,
    benefits,
    community,
    me,
    meta,
    savings,
    scholarships,
    stores,
)
from app.api import chat as chat_api
from app.core.config import settings
from app.core.db import init_db
from app.services.scheduler import shutdown_scheduler, start_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 개발 편의: 테이블 자동 생성(운영은 Alembic 사용 권장)
    if settings.app_env == "development":
        try:
            init_db()
        except Exception:  # noqa: BLE001
            logger.exception("init_db failed")
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(
    title="대학생 혜택 통합 서비스",
    version="0.2.0",
    description="주변 결제 할인(지도) + 장학금 매칭·초안 생성(챗봇)을 하나로",
    lifespan=lifespan,
)

# 허용 오리진은 CORS_ORIGINS 환경변수로 지정한다(쉼표 구분).
# 운영 모드에서 localhost가 남아 있으면 부팅이 실패한다(core.config).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(stores.router)
app.include_router(meta.router)
app.include_router(me.router)
app.include_router(applications.router)
app.include_router(scholarships.router)
app.include_router(ai.router)
app.include_router(savings.router)
app.include_router(benefits.router)
app.include_router(community.router)
app.include_router(admin.router)
app.include_router(admin.offer_report_router)
app.include_router(chat_api.router)
app.include_router(chat_api.index_router)


@app.get("/health", tags=["system"])
def health() -> dict:
    """liveness: 프로세스가 살아 있는지만 본다. 로드밸런서가 때린다."""
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
def ready() -> dict:
    """readiness: 의존성까지 확인한다. 트래픽을 받아도 되는지 판단용.

    DB가 죽었는데 /health 가 200이면 로드밸런서는 계속 트래픽을 보낸다.
    그래서 실제 질의 한 번으로 DB를 확인하고, 실패하면 503을 낸다.
    LLM은 없어도 규칙기반 폴백으로 서비스되므로 상태만 알리고 막지 않는다.
    """
    from sqlalchemy import text

    from app.core.db import engine
    from app.services.llm import has_llm

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        logger.exception("readiness: db check failed")
        db_ok = False

    body = {"status": "ok" if db_ok else "degraded", "db": db_ok, "llm": has_llm()}
    if not db_ok:
        raise HTTPException(status_code=503, detail=body)
    return body
