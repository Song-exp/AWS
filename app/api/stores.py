"""매장·혜택 조회 API(페이픽 지도 서비스).

간편결제 할인(StoreOffer, 매장별)과 카드 혜택(CardBenefit, 브랜드별)을
함께 반환한다. 카드 혜택 다수가 '간편결제 제외' 조건이라 두 혜택은 보통
동시 적용되지 않으므로, 합산하지 않고 **더 유리한 쪽을 추천**한다.
"""
from __future__ import annotations

import math
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.models.card import BenefitType, CardBenefit, Confidence
from app.models.store import PayMethod, Store, StoreCategory, StoreOffer
from app.services.card_normalize import store_brand_key

router = APIRouter(prefix="/stores", tags=["stores"])

_EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 간 거리(미터)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


class OfferOut(BaseModel):
    pay_method: PayMethod
    discount_rate: int
    condition_text: str | None = None

    class Config:
        from_attributes = True


class CardBenefitOut(BaseModel):
    id: int
    card_name: str
    issuer: str | None = None
    benefit_type: BenefitType
    value_min: float | None = None
    value_max: float | None = None
    benefit_text: str | None = None
    min_payment_krw: int | None = None
    min_payment_raw: str | None = None
    cap_text: str | None = None
    period_text: str | None = None
    conditions: list = []
    excludes_simple_pay: bool = False
    confidence: Confidence
    source_url: str | None = None


class BestDeal(BaseModel):
    """이 매장에서 가장 유리한 결제 방법."""

    kind: str                 # 'simple_pay' | 'card'
    label: str                # '네이버페이' | '하나 나라사랑카드(체크)'
    discount_rate: float      # 정률(%) 기준 비교값
    note: str | None = None


class StoreOut(BaseModel):
    id: int
    brand: str
    branch: str
    category: StoreCategory
    address: str | None = None
    lat: float
    lng: float
    mark: str | None = None
    color: str | None = None
    offers: list[OfferOut] = []
    card_benefits: list[CardBenefitOut] = []
    distance_m: float | None = None
    max_discount_rate: int = 0            # 간편결제 최대 할인율(기존 호환)
    max_card_discount_rate: float = 0     # 카드 최대 정률 할인율
    best_deal: BestDeal | None = None


def _active_offers(store: Store, pay: list[PayMethod] | None) -> list[StoreOffer]:
    today = date.today()
    result = []
    for o in store.offers:
        if not o.is_active:
            continue
        if o.valid_from and o.valid_from > today:
            continue
        if o.valid_to and o.valid_to < today:
            continue
        if pay and o.pay_method not in pay:
            continue
        result.append(o)
    return result


def _load_card_benefits(
    db: Session,
    include_unverified: bool,
    card_ids: list[int] | None = None,
) -> dict[str, list[CardBenefit]]:
    """brand_key -> 유효한 카드 혜택 목록.

    card_ids가 주어지면 사용자가 보유한 카드의 혜택만 반환한다(온보딩 프로필).
    """
    today = date.today()
    stmt = (
        select(CardBenefit)
        .where(
            CardBenefit.is_active.is_(True),
            CardBenefit.brand_key.is_not(None),
            CardBenefit.benefit_type != BenefitType.EXPIRED,
        )
        .options(selectinload(CardBenefit.card))
    )
    if not include_unverified:
        stmt = stmt.where(CardBenefit.confidence != Confidence.UNVERIFIED)
    if card_ids:
        stmt = stmt.where(CardBenefit.card_id.in_(card_ids))

    result: dict[str, list[CardBenefit]] = {}
    for b in db.scalars(stmt).all():
        # 기간 필터(무기한은 통과)
        if b.valid_from and b.valid_from > today:
            continue
        if b.valid_to and b.valid_to < today:
            continue
        result.setdefault(b.brand_key, []).append(b)
    return result


def _to_benefit_out(b: CardBenefit) -> CardBenefitOut:
    return CardBenefitOut(
        id=b.id,
        card_name=b.card.card_name if b.card else "(미상)",
        issuer=b.card.issuer if b.card else None,
        benefit_type=b.benefit_type,
        value_min=b.value_min,
        value_max=b.value_max,
        benefit_text=b.benefit_text,
        min_payment_krw=b.min_payment_krw,
        min_payment_raw=b.min_payment_raw,
        cap_text=b.cap_text,
        period_text=b.period_text,
        conditions=list(b.conditions or []),
        excludes_simple_pay=b.excludes_simple_pay,
        confidence=b.confidence,
        source_url=b.source_url,
    )


def _pick_best(offers: list[StoreOffer], benefits: list[CardBenefit]) -> BestDeal | None:
    """간편결제 vs 카드 중 더 유리한 쪽 선택.

    카드 혜택 범위값('10~30%')은 과대표시를 피하려 **최소값**으로 비교한다.
    정액/이벤트 혜택은 정률 비교가 불가하므로 후보에서 제외한다.
    """
    best: BestDeal | None = None

    for o in offers:
        if best is None or o.discount_rate > best.discount_rate:
            best = BestDeal(
                kind="simple_pay",
                label=o.pay_method.value,
                discount_rate=float(o.discount_rate),
                note=o.condition_text,
            )

    for b in benefits:
        if b.benefit_type != BenefitType.PERCENT or b.value_min is None:
            continue
        if best is None or b.value_min > best.discount_rate:
            note = "; ".join(b.conditions or []) or b.benefit_text
            best = BestDeal(
                kind="card",
                label=b.card.card_name if b.card else "(카드)",
                discount_rate=float(b.value_min),
                note=note,
            )
    return best


@router.get("/nearby", response_model=list[StoreOut])
def nearby_stores(
    lat: float | None = Query(default=None, description="현재 위치 위도"),
    lng: float | None = Query(default=None, description="현재 위치 경도"),
    radius_m: float = Query(default=2000, ge=50, le=20000, description="검색 반경(m)"),
    pay: list[PayMethod] | None = Query(default=None, description="결제수단 필터(복수 가능)"),
    category: list[StoreCategory] | None = Query(
        default=None, description="매장 카테고리 필터(편의점/카페/음식점/마트 등, 복수 가능)"
    ),
    card_ids: list[int] | None = Query(
        default=None, description="보유 카드 ID(복수). 지정 시 해당 카드 혜택만 표시"
    ),
    sort: str = Query(default="distance", pattern="^(distance|discount)$"),
    include_unverified: bool = Query(default=False, description="미확인 혜택 포함"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[StoreOut]:
    """주변 매장 + 간편결제 할인 + 브랜드 카드 혜택 조회."""
    stmt = select(Store).where(Store.is_active.is_(True)).options(selectinload(Store.offers))
    if category:
        stmt = stmt.where(Store.category.in_(category))
    stores = db.scalars(stmt).all()
    benefits_by_brand = _load_card_benefits(db, include_unverified, card_ids)

    items: list[StoreOut] = []
    for s in stores:
        offers = _active_offers(s, pay)
        # pay 필터는 간편결제 혜택이 있는 매장(편의점)에만 적용.
        # 카페/마트처럼 간편결제 offer가 없는 매장은 pay 필터로 배제하지 않는다.
        if pay and s.offers and not offers:
            continue

        distance = None
        if lat is not None and lng is not None:
            distance = haversine_m(lat, lng, s.lat, s.lng)
            if distance > radius_m:
                continue

        bkey = store_brand_key(s.brand)
        cbs = benefits_by_brand.get(bkey, [])
        pct_values = [b.value_min for b in cbs if b.benefit_type == BenefitType.PERCENT and b.value_min]

        items.append(
            StoreOut(
                id=s.id,
                brand=s.brand,
                branch=s.branch,
                category=s.category,
                address=s.address,
                lat=s.lat,
                lng=s.lng,
                mark=s.mark,
                color=s.color,
                offers=[OfferOut.model_validate(o) for o in offers],
                card_benefits=[_to_benefit_out(b) for b in cbs],
                distance_m=round(distance, 1) if distance is not None else None,
                max_discount_rate=max((o.discount_rate for o in offers), default=0),
                max_card_discount_rate=max(pct_values, default=0),
                best_deal=_pick_best(offers, cbs),
            )
        )

    if sort == "discount":
        # 간편결제/카드 중 더 큰 값으로 정렬
        items.sort(
            key=lambda x: max(x.max_discount_rate, x.max_card_discount_rate), reverse=True
        )
    else:
        items.sort(key=lambda x: (x.distance_m is None, x.distance_m or 0))

    return items[:limit]


@router.get("/{store_id}", response_model=StoreOut)
def get_store(
    store_id: int,
    include_unverified: bool = Query(default=False),
    card_ids: list[int] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> StoreOut:
    s = db.scalar(
        select(Store).where(Store.id == store_id).options(selectinload(Store.offers))
    )
    if s is None:
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

    offers = _active_offers(s, None)
    bkey = store_brand_key(s.brand)
    cbs = _load_card_benefits(db, include_unverified, card_ids).get(bkey, [])
    pct_values = [b.value_min for b in cbs if b.benefit_type == BenefitType.PERCENT and b.value_min]

    return StoreOut(
        id=s.id,
        brand=s.brand,
        branch=s.branch,
        category=s.category,
        address=s.address,
        lat=s.lat,
        lng=s.lng,
        mark=s.mark,
        color=s.color,
        offers=[OfferOut.model_validate(o) for o in offers],
        card_benefits=[_to_benefit_out(b) for b in cbs],
        max_discount_rate=max((o.discount_rate for o in offers), default=0),
        max_card_discount_rate=max(pct_values, default=0),
        best_deal=_pick_best(offers, cbs),
    )
