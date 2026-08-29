"""학생 제휴와 지역화폐 가맹점 혜택 모델."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import PKType
from app.models.store import StoreCategory


class LocalBenefitMerchant(Base):
    """주소 기반 제휴·지역화폐 가맹점 한 건.

    원본 Excel에는 좌표가 없으므로 주소와 장소검색어를 보존하고, 프론트의
    Kakao services가 실제 지도 좌표를 계산한다. lat/lng는 향후 서버 측
    지오코딩 결과를 캐시할 수 있도록 nullable로 둔다.
    """

    __tablename__ = "local_benefit_merchants"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    merchant_name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[StoreCategory] = mapped_column(
        Enum(StoreCategory, name="local_benefit_store_category"), index=True
    )
    category_label: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(500))
    search_query: Mapped[str] = mapped_column(String(700))
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    source_type: Mapped[str] = mapped_column(String(50), index=True)
    programs: Mapped[list] = mapped_column(JSON, default=list)
    credentials: Mapped[list] = mapped_column(JSON, default=list)
    requires: Mapped[str | None] = mapped_column(String(500))
    benefit_text: Mapped[str] = mapped_column(Text)
    discount_type: Mapped[str | None] = mapped_column(String(30))
    discount_value: Mapped[float | None] = mapped_column(Float)
    min_spend: Mapped[float | None] = mapped_column(Float)
    max_amount: Mapped[float | None] = mapped_column(Float)
    conditions: Mapped[str | None] = mapped_column(Text)
    valid_to: Mapped[date | None] = mapped_column(Date)
    confidence: Mapped[str | None] = mapped_column(String(20))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_local_benefit_category_active", "category", "is_active"),
    )
