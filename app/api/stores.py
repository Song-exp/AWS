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
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user
from app.models.card import BenefitType, CardBenefit, Confidence
from app.models.community import Report
from app.models.user import User
from app.models.store import PayMethod, Store, StoreCategory, StoreOffer
from app.models.local_benefit import LocalBenefitMerchant
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
    id: int
    pay_method: PayMethod
    discount_rate: int
    condition_text: str | None = None
    #: '이미 끝난 혜택이에요' 제보 수. 임계를 넘으면 프론트가 흐리게 표시한다.
    report_count: int = 0
    reported: bool = False
    #: 확인되지 않은 예시 값. 프론트가 '예시' 뱃지를 붙인다.
    is_sample: bool = False

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
    max_discount_rate: int = 0
    max_card_discount_rate: float = 0
    best_deal: BestDeal | None = None


class LocalBenefitOut(BaseModel):
    id: int
    source_key: str
    merchant_name: str
    category: StoreCategory
    category_label: str | None = None
    address: str | None = None
    search_query: str
    lat: float | None = None
    lng: float | None = None
    source_type: str
    programs: list[str] = []
    credentials: list[str] = []
    requires: str | None = None
    benefit_text: str
    discount_type: str | None = None
    discount_value: float | None = None
    min_spend: float | None = None
    max_amount: float | None = None
    conditions: str | None = None
    valid_to: date | None = None
    confidence: str | None = None
    source_url: str | None = None

    class Config:
        from_attributes = True


class LocalBenefitsPage(BaseModel):
    items: list[LocalBenefitOut]
    total: int
    offset: int
    limit: int


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


def _to_offer_out(
    o: StoreOffer, counts: dict[int, int], reported_ids: set[int]
) -> OfferOut:
    out = OfferOut.model_validate(o)
    out.report_count = counts.get(o.id, 0)
    out.reported = o.id in reported_ids
    return out


def _offer_report_counts(db: Session) -> dict[int, int]:
    """offer_id -> 제보 수. 매장마다 쿼리하면 N+1이 되므로 한 번에 읽는다."""
    rows = db.execute(
        select(Report.store_offer_id, func.count(Report.id))
        .where(Report.store_offer_id.is_not(None))
        .group_by(Report.store_offer_id)
    ).all()
    return {offer_id: cnt for offer_id, cnt in rows}


def _pick_best(
    offers: list[StoreOffer],
    benefits: list[CardBenefit],
    reported_offer_ids: set[int] = frozenset(),
) -> BestDeal | None:
    """간편결제 vs 카드 중 더 유리한 쪽 선택.

    카드 혜택 범위값('10~30%')은 과대표시를 피하려 **최소값**으로 비교한다.
    정액/이벤트 혜택은 정률 비교가 불가하므로 후보에서 제외한다.

    끝난 혜택으로 제보된 간편결제 할인은 추천에서 뺀다. 목록에는 남겨
    사용자가 판단하게 하되, **1순위로 밀어주는 것만은 막는다** — 여기가
    실제로 헛걸음이 발생하는 지점이다.
    """
    best: BestDeal | None = None

    for o in offers:
        if o.id in reported_offer_ids:
            continue
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
    report_counts = _offer_report_counts(db)
    threshold = settings.store_offer_report_threshold
    reported_ids = {
        oid for oid, cnt in report_counts.items() if threshold > 0 and cnt >= threshold
    }

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
                offers=[_to_offer_out(o, report_counts, reported_ids) for o in offers],
                card_benefits=[_to_benefit_out(b) for b in cbs],
                distance_m=round(distance, 1) if distance is not None else None,
                max_discount_rate=max((o.discount_rate for o in offers), default=0),
                max_card_discount_rate=max(pct_values, default=0),
                best_deal=_pick_best(offers, cbs, reported_ids),
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


@router.get("/local-benefits", response_model=LocalBenefitsPage)
def local_benefits(
    program: list[str] | None = Query(default=None, description="제휴/지역화폐 프로그램"),
    credential: list[str] | None = Query(default=None, description="학생증/톡학생증 인증"),
    category: list[StoreCategory] | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=60, ge=1, le=200),
    db: Session = Depends(get_db),
) -> LocalBenefitsPage:
    """주소 기반 학생제휴·온누리·서울Pay+·제로페이 가맹점 조회."""
    stmt = select(LocalBenefitMerchant).where(LocalBenefitMerchant.is_active.is_(True))
    if category:
        stmt = stmt.where(LocalBenefitMerchant.category.in_(category))
    rows = db.scalars(stmt.order_by(LocalBenefitMerchant.id)).all()

    requested_programs = set(program or [])
    requested_credentials = set(credential or [])
    query = q.strip().lower() if q else None
    filtered: list[LocalBenefitMerchant] = []
    for row in rows:
        if requested_programs and not requested_programs.intersection(row.programs or []):
            continue
        required_credentials = set(row.credentials or [])
        if required_credentials and not requested_credentials.intersection(required_credentials):
            continue
        if query:
            haystack = " ".join(
                value for value in (row.merchant_name, row.address, row.benefit_text) if value
            ).lower()
            if query not in haystack:
                continue
        filtered.append(row)

    page = filtered[offset : offset + limit]
    return LocalBenefitsPage(
        items=[LocalBenefitOut.model_validate(row) for row in page],
        total=len(filtered),
        offset=offset,
        limit=limit,
    )


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
    report_counts = _offer_report_counts(db)
    threshold = settings.store_offer_report_threshold
    reported_ids = {
        oid for oid, cnt in report_counts.items() if threshold > 0 and cnt >= threshold
    }
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
        offers=[_to_offer_out(o, report_counts, reported_ids) for o in offers],
        card_benefits=[_to_benefit_out(b) for b in cbs],
        max_discount_rate=max((o.discount_rate for o in offers), default=0),
        max_card_discount_rate=max(pct_values, default=0),
        best_deal=_pick_best(offers, cbs, reported_ids),
    )


class OfferReportOut(BaseModel):
    active: bool          # 내가 제보한 상태인가
    count: int            # 이 혜택의 총 제보 수
    flagged: bool         # 임계를 넘겨 추천에서 빠졌는가


@router.post("/offers/{offer_id}/report", response_model=OfferReportOut)
def report_offer(
    offer_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> OfferReportOut:
    """'이미 끝난 혜택이에요' 제보 토글.

    확인창도 사유 입력도 없다. 물어보면 안 누르고, 안 누르면 지도 데이터가
    영원히 낡은 채로 남는다. 오탭은 다시 눌러 취소한다.

    같은 사람의 중복 제보는 1건으로 본다(커뮤니티 신고와 같은 규칙).
    """
    offer = db.get(StoreOffer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="혜택을 찾을 수 없습니다.")

    row = db.scalar(
        select(Report).where(
            Report.store_offer_id == offer_id, Report.reporter_id == user.id
        )
    )
    if row is None:
        db.add(
            Report(
                store_offer_id=offer_id,
                reporter_id=user.id,
                reason="offer_expired",
            )
        )
        active = True
    else:
        db.delete(row)
        active = False
    db.commit()

    count = db.scalar(
        select(func.count(Report.id)).where(Report.store_offer_id == offer_id)
    ) or 0
    threshold = settings.store_offer_report_threshold
    return OfferReportOut(
        active=active,
        count=count,
        flagged=threshold > 0 and count >= threshold,
    )
