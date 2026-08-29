"""사용자 모델.

두 서비스(지도·챗봇)를 하나로 합치면서 공통 프로필이 필요해졌다.
- 챗봇: 소득분위·학점·지역 등 장학금 매칭 자격
- 지도: 선호 결제수단(카카오/토스/네이버페이)
기존 코드가 user_id(UUID)만 들고 있던 것을 실제 테이블로 승격한다.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import GUIDType, StrListType


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUIDType, primary_key=True, default=uuid.uuid4)

    nickname: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)

    # --- 장학금 매칭용 프로필 ---
    income_bracket: Mapped[int | None] = mapped_column(Integer)   # 소득분위 0~10
    gpa: Mapped[float | None] = mapped_column(Float)
    grade_level: Mapped[str | None] = mapped_column(String(10))   # '1'~'4'
    region: Mapped[str | None] = mapped_column(String(50))
    major: Mapped[str | None] = mapped_column(String(100))
    interests: Mapped[list[str]] = mapped_column(StrListType, default=list)

    # --- 지도(페이픽) 개인화 ---
    preferred_pay_methods: Mapped[list[str]] = mapped_column(StrListType, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
