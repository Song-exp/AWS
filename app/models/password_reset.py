"""비밀번호 재설정 토큰.

세션 토큰과 같은 원칙: 원문을 저장하지 않고 sha256 해시만 보관한다.
다만 성격이 달라 별도 테이블을 쓴다.
  - 수명이 짧다(기본 30분). 메일함이 털린 뒤 뒤늦게 쓰이는 것을 막는다.
  - 1회용이다. 한 번 쓴 링크는 다시 통하지 않는다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import GUIDType, PKType


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # 사용 시각. NULL이면 아직 안 쓴 토큰이다.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
