"""운영 관리 API: 수동 크롤 트리거 + 실행 이력 조회."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_admin
from app.crawlers.registry import run_daily_update
from app.models.crawl_run import CrawlRun, CrawlRunStatus

router = APIRouter(
    prefix="/admin/crawl",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


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


@router.post("/run", response_model=CrawlRunOut)
def trigger_run(db: Session = Depends(get_db)) -> CrawlRunOut:
    """일간 갱신(마감 삭제 + 신규 수집)을 수동 실행(동기)."""
    return CrawlRunOut.model_validate(run_daily_update(db, trigger="manual"))


@router.get("/runs", response_model=list[CrawlRunOut])
def list_runs(limit: int = 20, db: Session = Depends(get_db)) -> list[CrawlRunOut]:
    """최근 실행 이력 조회(최신순)."""
    rows = db.scalars(
        select(CrawlRun).order_by(CrawlRun.id.desc()).limit(limit)
    ).all()
    return [CrawlRunOut.model_validate(r) for r in rows]


# --- 끝난 혜택 제보 확인 ---
# 별도 라우터를 두는 이유는 prefix 가 /admin/crawl 이 아니기 때문이다.
offer_report_router = APIRouter(
    prefix="/admin/offer-reports",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class OfferReportRow(BaseModel):
    offer_id: int
    store_id: int
    store_label: str
    pay_method: str
    discount_rate: int
    report_count: int
    is_active: bool
    flagged: bool


@offer_report_router.get("", response_model=list[OfferReportRow])
def list_offer_reports(
    min_count: int = 1,
    db: Session = Depends(get_db),
) -> list[OfferReportRow]:
    """제보가 쌓인 혜택 목록. 많이 제보된 순.

    자동 비활성을 하지 않기로 했으므로 이 목록이 사람의 판단 지점이다.
    확인 후 store_offers.is_active 를 내린다.
    """
    from sqlalchemy import func

    from app.core.config import settings
    from app.models.community import Report
    from app.models.store import Store, StoreOffer

    rows = db.execute(
        select(StoreOffer, Store, func.count(Report.id).label("cnt"))
        .join(Report, Report.store_offer_id == StoreOffer.id)
        .join(Store, Store.id == StoreOffer.store_id)
        .group_by(StoreOffer.id, Store.id)
        .having(func.count(Report.id) >= min_count)
        .order_by(func.count(Report.id).desc())
    ).all()

    threshold = settings.store_offer_report_threshold
    return [
        OfferReportRow(
            offer_id=offer.id,
            store_id=store.id,
            store_label=f"{store.brand} {store.branch}",
            pay_method=offer.pay_method.value,
            discount_rate=offer.discount_rate,
            report_count=cnt,
            is_active=offer.is_active,
            flagged=threshold > 0 and cnt >= threshold,
        )
        for offer, store, cnt in rows
    ]
