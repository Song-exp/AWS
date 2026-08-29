"""온보딩 선택 옵션 API.

첫 화면에서 사용자가 자기 정보를 고를 때 쓰는 목록을 제공한다.
카드·간편결제는 DB 실데이터를 기반으로 하고, 통신사는 아직 혜택
데이터가 없어 정적 목록만 제공한다(선택은 저장되지만 필터에는 미반영).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.card import Card, CardBenefit
from app.models.store import PayMethod, StoreCategory

router = APIRouter(prefix="/meta", tags=["meta"])

_PAY_LABELS = {
    PayMethod.KAKAO: "카카오페이",
    PayMethod.TOSS: "토스페이",
    PayMethod.NAVER: "네이버페이",
}

_CATEGORY_LABELS = {
    StoreCategory.CONVENIENCE: "편의점",
    StoreCategory.CAFE: "카페",
    StoreCategory.RESTAURANT: "음식점",
    StoreCategory.MART: "마트",
    StoreCategory.BAKERY: "베이커리",
    StoreCategory.HNB: "H&B",
    StoreCategory.OTHER: "기타",
}

# 통신사: 현재 혜택 데이터가 없어 선택용 정적 목록만 제공한다.
_TELECOMS = ["SKT", "KT", "LG U+", "알뜰폰", "해당 없음"]


class CardOption(BaseModel):
    id: int
    card_name: str
    issuer: str | None = None
    benefit_count: int = 0


class PayOption(BaseModel):
    value: PayMethod
    label: str


class CategoryOption(BaseModel):
    value: StoreCategory
    label: str


class OptionsOut(BaseModel):
    cards: list[CardOption]
    pay_methods: list[PayOption]
    categories: list[CategoryOption]
    telecoms: list[str]
    telecom_supported: bool = False  # 통신사 혜택 데이터 보유 여부


@router.get("/options", response_model=OptionsOut)
def get_options(db: Session = Depends(get_db)) -> OptionsOut:
    """온보딩에서 고를 수 있는 항목 목록."""
    rows = db.execute(
        select(Card, func.count(CardBenefit.id))
        .outerjoin(CardBenefit, CardBenefit.card_id == Card.id)
        .group_by(Card.id)
        .order_by(Card.card_name)
    ).all()

    cards = [
        CardOption(
            id=c.id,
            card_name=c.card_name,
            issuer=c.issuer,
            benefit_count=int(cnt or 0),
        )
        for c, cnt in rows
    ]

    return OptionsOut(
        cards=cards,
        pay_methods=[PayOption(value=m, label=_PAY_LABELS[m]) for m in PayMethod],
        categories=[
            CategoryOption(value=cat, label=_CATEGORY_LABELS[cat]) for cat in StoreCategory
        ],
        telecoms=_TELECOMS,
        telecom_supported=False,
    )
