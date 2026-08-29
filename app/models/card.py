"""카드 및 브랜드 단위 카드 혜택 모델.

기존 StoreOffer(매장 × 간편결제)와 성격이 다르다:
  - StoreOffer : 매장별 간편결제(카카오/토스/네이버) 할인
  - CardBenefit: **브랜드 전체**(CU 전점 등)에 적용되는 카드사 혜택

그래서 매장마다 복제하지 않고 brand_key로 조인한다. 카드 혜택 다수가
'간편결제 제외' 조건을 가지므로 두 혜택은 보통 동시 적용되지 않는다
(excludes_simple_pay 플래그로 표현).
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.types import JSONType, PKType, StrListType


class BenefitType(str, enum.Enum):
    PERCENT = "percent"       # 정률 할인(%)
    AMOUNT = "amount"         # 정액 할인(원)
    CASHBACK = "cashback"     # 캐시백
    EVENT = "event"           # 금액 미확정 행사
    UNVERIFIED = "unverified"
    EXPIRED = "expired"


class Confidence(str, enum.Enum):
    CONFIRMED = "confirmed"       # 공식 확인
    CONDITIONAL = "conditional"   # 대상카드 등 일부 전제 남음
    UNVERIFIED = "unverified"     # 정적 확인 불가


class PeriodType(str, enum.Enum):
    ALWAYS_ON = "always_on"
    MONTHLY = "monthly_aug"
    WEEK4 = "week4_aug"


class Card(Base):
    """카드 마스터."""

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    card_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)  # card_id 또는 정규화 이름
    card_name: Mapped[str] = mapped_column(String(200))
    issuer: Mapped[str | None] = mapped_column(String(100))          # KB국민카드, 하나카드...
    issuance_status: Mapped[str | None] = mapped_column(String(200))  # '2025-12-24 신규발급 종료'

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    benefits: Mapped[list["CardBenefit"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )


class CardBenefit(Base):
    """카드 × 브랜드 혜택 1건."""

    __tablename__ = "card_benefits"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), index=True)

    # 중복 적재 방지용 키(카드+가맹점원문+혜택텍스트+기간)
    dedup_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    merchant_raw: Mapped[str] = mapped_column(String(200))   # 원본 표기 'GS25 / GS더프레시'
    brand_key: Mapped[str | None] = mapped_column(String(50), index=True)  # 정규화 'GS25'
    category: Mapped[str | None] = mapped_column(String(50))

    benefit_type: Mapped[BenefitType] = mapped_column(Enum(BenefitType, name="benefit_type"))
    # '5~20' 같은 범위 대응. 정렬/비교는 min을 보수적으로 사용.
    value_min: Mapped[float | None] = mapped_column(Float)
    value_max: Mapped[float | None] = mapped_column(Float)
    benefit_text: Mapped[str | None] = mapped_column(String(300))  # 표시용 원문

    min_payment_krw: Mapped[int | None] = mapped_column(Integer)
    min_payment_raw: Mapped[str | None] = mapped_column(String(100))  # '건당 1,000엔(JPY)'
    cap_text: Mapped[str | None] = mapped_column(String(200))

    period_type: Mapped[PeriodType | None] = mapped_column(Enum(PeriodType, name="period_type"))
    period_text: Mapped[str | None] = mapped_column(String(120))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)

    conditions: Mapped[list] = mapped_column(StrListType, default=list)
    # 간편결제와 동시 적용 불가 여부(조건 텍스트에서 파생)
    excludes_simple_pay: Mapped[bool] = mapped_column(Boolean, default=False)
    stackable_note: Mapped[str | None] = mapped_column(String(200))

    confidence: Mapped[Confidence] = mapped_column(
        Enum(Confidence, name="benefit_confidence"), default=Confidence.CONFIRMED
    )
    source_url: Mapped[str | None] = mapped_column(Text)
    source_as_of: Mapped[date | None] = mapped_column(Date)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    card: Mapped["Card"] = relationship(back_populates="benefits")

    __table_args__ = (
        Index("ix_card_benefits_brand_active", "brand_key", "is_active"),
    )
