"""FastAPI 앱 진입점.

실행: uvicorn app.main:app --reload

통합 서비스:
  - 페이픽(지도): 주변 편의점 간편결제 할인 (/stores)
  - 장학금 챗봇: 매칭·초안·아카이빙 (/chat, /scholarships, /ai, /applications)
월간 크롤 스케줄러를 lifespan에서 start/stop 한다.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, ai, applications, me, meta, scholarships, stores
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

# 프론트(Vite dev server) 연동용 CORS.
# 주의: 배포 시에는 실제 도메인만 허용하도록 좁혀야 한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stores.router)
app.include_router(meta.router)
app.include_router(me.router)
app.include_router(applications.router)
app.include_router(scholarships.router)
app.include_router(ai.router)
app.include_router(admin.router)
app.include_router(chat_api.router)
app.include_router(chat_api.index_router)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}
