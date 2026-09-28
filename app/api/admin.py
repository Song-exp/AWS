"""운영 관리 API: 수동 크롤 트리거 + 실행 이력 조회."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Response
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


# --- 커뮤니티 신고 처리 ---
# 신고는 쌓이기만 하고 볼 방법이 없었다. 익명 게시판에서는 이 목록과 삭제
# 권한이 운영자의 유일한 개입 수단이다. 자동 숨김은 하지 않는다. 몇 명이
# 몰려 신고하면 정상 글이 사라지기 때문에 마지막 판단은 사람이 한다.
moderation_router = APIRouter(
    prefix="/admin/moderation",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class ReportedItem(BaseModel):
    kind: str  # "post" | "comment"
    id: int
    post_id: int
    title: str | None = None
    excerpt: str
    report_count: int
    reasons: list[str]
    created_at: datetime | None = None


@moderation_router.get("/reports", response_model=list[ReportedItem])
def list_reported(min_count: int = 1, db: Session = Depends(get_db)) -> list[ReportedItem]:
    """신고가 쌓인 글·댓글. 많이 신고된 순. 이미 삭제된 것은 빼고 보여준다."""
    from sqlalchemy import func

    from app.models.community import Comment, Post, Report

    items: list[ReportedItem] = []
    for model, fk, kind in ((Post, Report.post_id, "post"), (Comment, Report.comment_id, "comment")):
        rows = db.execute(
            select(model, func.count(Report.id))
            .join(Report, fk == model.id)
            .where(model.deleted_at.is_(None))
            .group_by(model.id)
            .having(func.count(Report.id) >= min_count)
        ).all()
        for row, cnt in rows:
            reasons = db.scalars(select(Report.reason).where(fk == row.id)).all()
            items.append(
                ReportedItem(
                    kind=kind,
                    id=row.id,
                    post_id=row.id if kind == "post" else row.post_id,
                    title=getattr(row, "title", None),
                    excerpt=(row.body or "")[:200],
                    report_count=cnt,
                    reasons=list(reasons),
                    created_at=row.created_at,
                )
            )
    items.sort(key=lambda i: i.report_count, reverse=True)
    return items


@moderation_router.delete("/posts/{post_id}", status_code=204, response_class=Response)
def remove_post(post_id: int, db: Session = Depends(get_db)) -> Response:
    """글 삭제. 작성자 본인 삭제와 같은 소프트 삭제라 댓글 흐름은 남는다."""
    from datetime import timezone

    from fastapi import HTTPException

    from app.api.community import _image_path
    from app.models.community import Post

    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(404, "글을 찾을 수 없습니다.")
    post.deleted_at = datetime.now(timezone.utc)
    names, post.image_names = post.image_names or [], []
    db.commit()
    for name in names:
        _image_path(name).unlink(missing_ok=True)
    return Response(status_code=204)


@moderation_router.delete("/comments/{comment_id}", status_code=204, response_class=Response)
def remove_comment(comment_id: int, db: Session = Depends(get_db)) -> Response:
    from datetime import timezone

    from fastapi import HTTPException

    from app.models.community import Comment, Post

    comment = db.get(Comment, comment_id)
    if comment is None or comment.deleted_at is not None:
        raise HTTPException(404, "댓글을 찾을 수 없습니다.")
    comment.deleted_at = datetime.now(timezone.utc)
    post = db.get(Post, comment.post_id)
    if post and post.comment_count > 0:
        post.comment_count -= 1
    db.commit()
    return Response(status_code=204)


@moderation_router.delete("/{kind}/{item_id}/reports", status_code=204, response_class=Response)
def dismiss_reports(kind: str, item_id: int, db: Session = Depends(get_db)) -> Response:
    """문제없는 글이면 신고를 기각한다. 작성자 등급 강등도 함께 풀린다."""
    from fastapi import HTTPException
    from sqlalchemy import delete

    from app.models.community import Report

    column = {"posts": Report.post_id, "comments": Report.comment_id}.get(kind)
    if column is None:
        raise HTTPException(404, "posts 또는 comments 만 가능합니다.")
    db.execute(delete(Report).where(column == item_id))
    db.commit()
    return Response(status_code=204)
