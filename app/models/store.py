"""매장 및 결제수단별 할인 혜택 모델(페이픽 지도 서비스).

기존 프론트(app.js)에 하드코딩돼 있던 stores/standardOffers를 DB로 이관한다.
프론트 하드코딩은 혜택이 바뀔 때마다 배포가 필요해 운영이 불가능하므로,
매장·혜택을 분리하고 혜택에 유효기간을 둔다.
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.types import PKType


class PayMethod(str, enum.Enum):
    """간편결제 수단."""

    KAKAO = "kakao"
    TOSS = "toss"
    NAVER = "naver"


class StoreCategory(str, enum.Enum):
    """매장 오프라인 카테고리(지도 필터용)."""

    CONVENIENCE = "convenience"   # 편의점
    CAFE = "cafe"                 # 카페
    RESTAURANT = "restaurant"     # 음식점
    MART = "mart"                 # 마트/슈퍼
    BAKERY = "bakery"             # 베이커리
    HNB = "hnb"                   # 헬스&뷰티(올리브영 등)
    OTHER = "other"


class Store(Base):
    """매장(편의점·카페·음식점·마트 등)."""

    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)

    brand: Mapped[str] = mapped_column(String(100), index=True)   # CU, GS25, 스타벅스...
    branch: Mapped[str] = mapped_column(String(150))              # 경희대점
    category: Mapped[StoreCategory] = mapped_column(
        Enum(StoreCategory, name="store_category"),
        default=StoreCategory.CONVENIENCE,
        index=True,
    )
    address: Mapped[str | None] = mapped_column(String(300))

    # 위치 기반 조회용
    lat: Mapped[float] = mapped_column(Float, index=True)
    lng: Mapped[float] = mapped_column(Float, index=True)

    # 지도 마커 표시용(프론트 렌더링 메타)
    mark: Mapped[str | None] = mapped_column(String(10))          # 'CU', 'GS', '7', '24'
    color: Mapped[str | None] = mapped_column(String(20))         # '#7b2cbf'

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    offers: Mapped[list["StoreOffer"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # 동일 브랜드-지점 중복 적재 방지
        UniqueConstraint("brand", "branch", name="uq_store_brand_branch"),
        # 위치 범위 조회 가속
        Index("ix_stores_lat_lng", "lat", "lng"),
    )


class StoreOffer(Base):
    """매장 × 결제수단 할인 혜택."""

    __tablename__ = "store_offers"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )

    pay_method: Mapped[PayMethod] = mapped_column(Enum(PayMethod, name="pay_method"), index=True)
    discount_rate: Mapped[int] = mapped_column(Integer)            # 퍼센트 (5, 7, 10)
    condition_text: Mapped[str | None] = mapped_column(String(300))  # '1만원 이상 결제 · 최대 2천원'

    # 프로모션 기간(월별로 바뀌므로 필수)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    store: Mapped["Store"] = relationship(back_populates="offers")

    __table_args__ = (
        UniqueConstraint("store_id", "pay_method", name="uq_offer_store_paymethod"),
    )
