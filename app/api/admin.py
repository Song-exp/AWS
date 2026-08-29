"""운영 관리 API: 수동 크롤 트리거 + 실행 이력 조회."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.crawlers.registry import run_monthly_update
from app.models.crawl_run import CrawlRun, CrawlRunStatus

router = APIRouter(prefix="/admin/crawl", tags=["admin"])


class CrawlRunOut(BaseModel):
    id: int
    trigger: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    target_months: list = []
    total_fetched: int
    total_saved: int
    total_expired: int
    per_platform: list = []
    status: CrawlRunStatus
    error: str | None = None

    class Config:
        from_attributes = True


class RunTriggerRequest(BaseModel):
    # 선택: 특정 (연,월) 지정. 미지정 시 당월+익월 자동.
    target_months: list[list[int]] | None = None


@router.post("/run", response_model=CrawlRunOut)
def trigger_run(
    payload: RunTriggerRequest | None = None,
    db: Session = Depends(get_db),
) -> CrawlRunOut:
    """월간 갱신을 수동 실행(동기). 대상 월 미지정 시 당월+익월."""
    months = None
    if payload and payload.target_months:
        months = {(m[0], m[1]) for m in payload.target_months}
    run = run_monthly_update(db, trigger="manual", target_months=months)
    return CrawlRunOut.model_validate(run)


@router.get("/runs", response_model=list[CrawlRunOut])
def list_runs(limit: int = 20, db: Session = Depends(get_db)) -> list[CrawlRunOut]:
    """최근 실행 이력 조회(최신순)."""
    rows = db.scalars(
        select(CrawlRun).order_by(CrawlRun.id.desc()).limit(limit)
    ).all()
    return [CrawlRunOut.model_validate(r) for r in rows]
