"""로그인 세션 모델.

무상태 토큰(JWT) 대신 DB 세션을 쓴다:
  - 로그아웃이 실제로 동작한다(무상태 토큰은 만료 전까지 무효화가 안 된다).
  - 계정 탈취 시 전 기기 로그아웃이 가능하다.
  - 라이브러리가 필요 없다.
비용은 요청당 조회 1회인데, 이미 매 요청 DB를 쓰므로 실질 부담이 없다.

주의: 토큰 원문은 저장하지 않는다. DB가 유출돼도 세션을 재사용하지 못하도록
해시만 보관한다(비밀번호와 같은 이유).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.types import GUIDType, PKType


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # sha256(raw token). 원문은 쿠키에만 존재한다.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # 로그아웃 시각. NULL이면 유효한 세션이다.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship()  # noqa: F821
