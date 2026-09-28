"""세이빙 대시보드 API(기획서 3.3).

'소비 완료' 토글 → 절감액 누적 → 체감 가능한 보상으로 환산.

KPI 연결:
  - 유저당 월평균 지출 절감액        → summary.month_saved
  - 혜택 조회 후 실소비 전환율        → summary.conversion_rate
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user
from app.models.user import User
from app.models.saving import SavingKind, SavingRecord
from app.models.store import SPEND_LABELS, STORE_TO_SPEND, SpendCategory, Store
from app.services.tier import TierOut, compute_tier

# 절감 이력은 개인 데이터다. 전부 로그인을 요구한다.
router = APIRouter(
    prefix="/savings",
    tags=["savings"],
    dependencies=[Depends(current_user)],
)

KST = timezone(timedelta(hours=9))

# 절감액을 체감시키는 환산 기준. 학교 앞 물가 기준이라 바뀔 수 있어 한곳에 모은다.
# ponytail: 상수 테이블로 충분하다. 지역·물가별로 달라져야 하면 그때 DB로 승격.
_REWARDS: list[tuple[str, int]] = [
    ("학식", 6000),
    ("아메리카노", 4500),
    ("편의점 삼각김밥", 1500),
]


def _month_start_utc(now_kst: datetime) -> datetime:
    """'이번 달'은 KST 기준이지만, 비교는 저장 형식과 같은 UTC로 한다.

    한국 서비스라 월 경계는 KST 자정이어야 한다. 그런데 값은 UTC로 저장되므로
    KST 월초를 UTC로 변환해 비교해야 월초 9시간이 지난달로 새지 않는다.
    """
    start_kst = now_kst.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start_kst.astimezone(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    """저장값을 UTC aware 로 정규화한다.

    SQLite는 tz를 버리고 naive를 돌려준다. 저장은 UTC로 하므로 naive는
    UTC로 해석해야 한다(KST로 간주하면 9시간 어긋난다).
    """
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class SpendIn(BaseModel):
    """소비 완료 토글. 소유자는 세션에서 판단한다."""

    store_id: int | None = None
    store_label: str = ""
    # 매장이 없는 절감(교통 정액권·구독 전환·지원금)은 분야를 직접 준다.
    # 매장이 있으면 업종에서 유도하므로 비워도 된다.
    category: SpendCategory | None = None
    original_amount: float = Field(gt=0, description="할인 전 결제 예정 금액(원)")
    final_amount: float = Field(ge=0, description="실제 결제 금액(원)")
    method_label: str = Field(default="", description="'네이버페이 10%' 등 사용한 수단")


class ViewIn(BaseModel):
    """매장 혜택 조회 이벤트(전환율 분모)."""

    store_id: int | None = None
    store_label: str = ""
    category: SpendCategory | None = None


class SavingOut(BaseModel):
    id: int
    kind: str
    store_label: str
    category: SpendCategory | None = None
    category_label: str | None = None
    original_amount: float
    final_amount: float
    saved_amount: float
    method_label: str
    created_at: str | None = None


class RewardOut(BaseModel):
    label: str          # '학식'
    count: int          # 5
    message: str        # '이번 달 학식 5그릇 값 세이브 완료!'


class CategorySavingOut(BaseModel):
    category: SpendCategory | None = None
    label: str
    saved: float
    count: int


class SummaryOut(BaseModel):
    user_id: str
    month: str                  # '2026-09'
    month_saved: float          # 이번 달 누적 절감액
    total_saved: float          # 전체 누적
    month_count: int            # 이번 달 소비 완료 건수
    viewed_count: int           # 이번 달 혜택 조회 건수
    conversion_rate: float      # 소비완료 / 조회 (KPI 목표 0.25)
    reward: RewardOut | None = None
    tier: TierOut | None = None
    # 이번 달 분야별 절감. 대시보드가 '어디서 아꼈나'를 보여주는 축이다.
    by_category: list[CategorySavingOut] = []
    recent: list[SavingOut] = []


def _reward_for(amount: float) -> RewardOut | None:
    """절감액을 가장 체감되는 단위로 환산한다.

    큰 단위부터 보고 1개 이상 환산되는 첫 항목을 쓴다. '삼각김밥 40개'보다
    '학식 6그릇'이 와닿기 때문이다.
    """
    for label, unit in _REWARDS:
        count = int(amount // unit)
        if count >= 1:
            suffix = "그릇" if label == "학식" else "개"
            return RewardOut(
                label=label,
                count=count,
                message=f"이번 달 {label} {count}{suffix} 값 세이브 완료!",
            )
    return None


def _to_out(r: SavingRecord) -> SavingOut:
    created = _as_aware(r.created_at)
    # 표시는 사용자가 사는 시간대(KST)로 변환한다.
    created = created.astimezone(KST) if created else None
    return SavingOut(
        id=r.id,
        kind=r.kind.value if hasattr(r.kind, "value") else str(r.kind),
        store_label=r.store_label,
        category=r.category,
        category_label=SPEND_LABELS.get(r.category) if r.category else None,
        original_amount=r.original_amount,
        final_amount=r.final_amount,
        saved_amount=r.saved_amount,
        method_label=r.method_label,
        created_at=created.isoformat() if created else None,
    )


@router.post("/spend", response_model=SavingOut, status_code=201)
def record_spend(
    payload: SpendIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SavingOut:
    """'소비 완료' 체크. 절감액을 계산해 누적에 반영한다."""
    if payload.final_amount > payload.original_amount:
        raise HTTPException(
            status_code=422,
            detail="실제 결제 금액이 할인 전 금액보다 클 수 없습니다.",
        )

    label = payload.store_label
    category = payload.category
    if payload.store_id:
        store = db.get(Store, payload.store_id)
        if store:
            if not label:
                label = f"{store.brand} {store.branch}"
            # 지도에서 온 기록은 업종이 분야를 결정한다. 클라이언트가
            # 분야를 안 보내도 대시보드가 비지 않게 서버에서 채운다.
            if category is None:
                category = STORE_TO_SPEND.get(store.category)

    row = SavingRecord(
        user_id=user.id,
        kind=SavingKind.SPENT,
        store_id=payload.store_id,
        store_label=label,
        category=category,
        original_amount=payload.original_amount,
        final_amount=payload.final_amount,
        saved_amount=round(payload.original_amount - payload.final_amount, 2),
        method_label=payload.method_label,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.post("/view", status_code=204, response_class=Response)
def record_view(
    payload: ViewIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """매장 혜택 조회 기록. 전환율 KPI의 분모가 된다."""
    db.add(
        SavingRecord(
            user_id=user.id,
            kind=SavingKind.VIEWED,
            category=payload.category,
            store_id=payload.store_id,
            store_label=payload.store_label,
        )
    )
    db.commit()
    return Response(status_code=204)


@router.get("/summary", response_model=SummaryOut)
def summary(
    limit: int = Query(default=10, ge=1, le=50, description="최근 내역 개수"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SummaryOut:
    """월간 누적 절감액 + 보상 환산 + 전환율."""
    user_id = user.id
    now = datetime.now(KST)
    start = _month_start_utc(now)

    def _agg(kind: SavingKind, since: datetime | None):
        stmt = select(
            func.coalesce(func.sum(SavingRecord.saved_amount), 0.0),
            func.count(SavingRecord.id),
        ).where(SavingRecord.user_id == user_id, SavingRecord.kind == kind)
        if since is not None:
            stmt = stmt.where(SavingRecord.created_at >= since)
        return db.execute(stmt).one()

    month_saved, month_count = _agg(SavingKind.SPENT, start)
    total_saved, _ = _agg(SavingKind.SPENT, None)
    _, viewed_count = _agg(SavingKind.VIEWED, start)

    by_cat_rows = db.execute(
        select(
            SavingRecord.category,
            func.coalesce(func.sum(SavingRecord.saved_amount), 0.0),
            func.count(SavingRecord.id),
        )
        .where(
            SavingRecord.user_id == user_id,
            SavingRecord.kind == SavingKind.SPENT,
            SavingRecord.created_at >= start,
        )
        .group_by(SavingRecord.category)
    ).all()
    by_category = sorted(
        (
            CategorySavingOut(
                category=cat,
                label=SPEND_LABELS.get(cat, "기타") if cat else "기타",
                saved=round(float(amount), 2),
                count=cnt,
            )
            for cat, amount, cnt in by_cat_rows
        ),
        key=lambda c: c.saved,
        reverse=True,
    )

    recent = db.scalars(
        select(SavingRecord)
        .where(SavingRecord.user_id == user_id, SavingRecord.kind == SavingKind.SPENT)
        .order_by(SavingRecord.id.desc())
        .limit(limit)
    ).all()

    return SummaryOut(
        user_id=str(user_id),
        month=now.strftime("%Y-%m"),
        month_saved=round(float(month_saved), 2),
        total_saved=round(float(total_saved), 2),
        month_count=month_count,
        viewed_count=viewed_count,
        # 조회가 0이면 전환율은 정의되지 않는다. 0으로 두어 UI가 나누기를 하지 않게 한다.
        conversion_rate=round(month_count / viewed_count, 4) if viewed_count else 0.0,
        reward=_reward_for(float(month_saved)),
        tier=compute_tier(db, user_id),
        by_category=by_category,
        recent=[_to_out(r) for r in recent],
    )
