"""사용자 신청서 이력 모델.

두 가지 경로로 데이터가 쌓인다(플라이휠):
  1) UPLOADED  - 사용자가 과거 신청서 파일을 업로드
  2) GENERATED - 이 서비스로 작성/제출한 신청서가 자동 축적
두 경로 모두 초안 생성의 RAG 소스가 된다.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.config import settings
from app.core.db import Base
from app.core.types import GUIDType, PKType, StrListType, vector_column


class ApplicationSource(str, enum.Enum):
    UPLOADED = "uploaded"    # 최초 파일 업로드
    GENERATED = "generated"  # 서비스로 작성 → 자동 축적 (플라이휠)


class ApplicationResult(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DocType(str, enum.Enum):
    SELF_INTRO = "self_intro"     # 자기소개서
    STUDY_PLAN = "study_plan"     # 학업계획서
    ACTIVITY = "activity"         # 활동/경력
    OTHER = "other"


class UserApplication(Base):
    """한 건의 장학금 신청 이력."""

    __tablename__ = "user_applications"

    id: Mapped[uuid.UUID] = mapped_column(GUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUIDType, index=True)

    scholarship_name: Mapped[str] = mapped_column(String(500))
    organization: Mapped[str | None] = mapped_column(String(300))

    # 이 서비스로 작성한 경우 원본 공고와 연결(선택)
    scholarship_id: Mapped[int | None] = mapped_column(
        ForeignKey("scholarships.id", ondelete="SET NULL"), nullable=True
    )

    source: Mapped[ApplicationSource] = mapped_column(
        Enum(ApplicationSource, name="application_source"), index=True
    )
    result: Mapped[ApplicationResult] = mapped_column(
        Enum(ApplicationResult, name="application_result"), default=ApplicationResult.DRAFT
    )

    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(StrListType, default=list)

    # 초안 생성 시 이 이력을 참조에 쓸지 사용자가 통제(프라이버시)
    is_reusable: Mapped[bool] = mapped_column(Boolean, default=True)

    # 업로드 원본 파일 경로(있으면)
    source_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    documents: Mapped[list["ApplicationDocument"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationDocument(Base):
    """신청서 내 문항 단위 답변. 문항별로 저장해야 새 공고의 유사 문항에 매칭 가능."""

    __tablename__ = "application_documents"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_applications.id", ondelete="CASCADE"), index=True
    )

    doc_type: Mapped[DocType] = mapped_column(Enum(DocType, name="doc_type"), default=DocType.OTHER)
    prompt_question: Mapped[str | None] = mapped_column(Text)  # 예: "지원동기를 서술하시오"
    content_text: Mapped[str] = mapped_column(Text)           # 실제 작성 답변
    char_count: Mapped[int] = mapped_column(Integer, default=0)

    embedding_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|indexed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped["UserApplication"] = relationship(back_populates="documents")
    embeddings: Mapped[list["DocumentEmbedding"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    @validates("content_text")
    def _strip_rrn(self, _key: str, value: str) -> str:
        """저장 직전에 주민등록번호를 지운다.

        본문이 들어오는 경로는 업로드 추출·직접 작성·수정 세 군데다. 각 경로에
        따로 붙이면 새 경로가 생길 때 빠뜨린다. 모든 경로가 이 속성 대입을
        지나므로 여기서 한 번만 막는다. DB에서 읽어올 때는 호출되지 않는다.
        """
        from app.utils.pii import strip_rrn
        from app.utils.text import strip_nul

        # NUL 은 PostgreSQL text 컬럼이 받지 못한다. PDF·한글 문서 추출에서
        # 섞여 들어오므로 같은 지점에서 함께 지운다.
        return strip_nul(strip_rrn(value))


class DocumentEmbedding(Base):
    """과거 답변 청크의 임베딩. 문항 유사도 매칭 + 초안 생성 RAG 소스."""

    __tablename__ = "document_embeddings"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("application_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(vector_column(settings.embedding_dim))

    document: Mapped["ApplicationDocument"] = relationship(back_populates="embeddings")
