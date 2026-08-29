"""크롤링으로 수집한 공고(장학금/정부혜택) 모델."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.db import Base
from app.core.types import JSONType, PKType, StrListType, vector_column


class SourceType(str, enum.Enum):
    """공공(정부혜택) vs 민간(장학금)."""

    PUBLIC = "public"    # 정부 혜택 - 공공기관
    PRIVATE = "private"  # 장학금 - 민간 플랫폼


class Category(str, enum.Enum):
    SCHOLARSHIP = "scholarship"       # 장학금
    GOV_BENEFIT = "gov_benefit"       # 정부지원금/혜택


class PostingStatus(str, enum.Enum):
    OPEN = "open"
    CLOSING_SOON = "closing_soon"
    CLOSED = "closed"
    SCHEDULE_CHANGED = "schedule_changed"
    NEEDS_REVIEW = "needs_review"     # 파싱 실패 등 - 사용자 미노출


class Scholarship(Base):
    """수집 공고. 장학금(민간) 또는 정부혜택(공공)을 함께 담는다."""

    __tablename__ = "scholarships"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)

    # 멱등성: source_platform + 원본 게시글 ID 해시
    content_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    title: Mapped[str] = mapped_column(String(500))
    organization: Mapped[str | None] = mapped_column(String(300))
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type"))
    category: Mapped[Category] = mapped_column(Enum(Category, name="category"))
    source_platform: Mapped[str] = mapped_column(String(100), index=True)
    source_url: Mapped[str] = mapped_column(Text)

    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    recruit_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 게시판 등록일. 마감일을 목록에 노출하지 않는 사이트(대학 장학공지 등)가 많아,
    # '최근 등록 = 모집중'으로 판단하기 위한 근거로 사용한다.
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # 자격/혜택은 정형+비정형 혼재 → JSONB로 유연 저장
    eligibility: Mapped[dict] = mapped_column(JSONType, default=dict)   # income_bracket, gpa_min, region, major...
    benefit: Mapped[dict] = mapped_column(JSONType, default=dict)       # type, amount_krw, amount_desc
    required_documents: Mapped[list[str]] = mapped_column(StrListType, default=list)

    body_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[PostingStatus] = mapped_column(
        Enum(PostingStatus, name="posting_status"), default=PostingStatus.OPEN, index=True
    )

    # 변경 감지 및 운영
    content_hash: Mapped[str | None] = mapped_column(String(64))
    crawled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    embeddings: Mapped[list["ScholarshipEmbedding"]] = relationship(
        back_populates="scholarship", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # 8월 필터/임박순 정렬에 자주 쓰이는 복합 인덱스
        Index("ix_scholarships_cat_deadline", "category", "deadline_at"),
    )


class ScholarshipEmbedding(Base):
    """공고 본문을 의미 청크로 나눠 임베딩한 벡터."""

    __tablename__ = "scholarship_embeddings"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    scholarship_id: Mapped[int] = mapped_column(
        ForeignKey("scholarships.id", ondelete="CASCADE"), index=True
    )
    chunk_type: Mapped[str] = mapped_column(String(30))  # eligibility|benefit|documents|body
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(vector_column(settings.embedding_dim))

    scholarship: Mapped["Scholarship"] = relationship(back_populates="embeddings")
