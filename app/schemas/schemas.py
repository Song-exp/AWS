"""API 요청/응답 스키마."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.application import (
    ApplicationResult,
    ApplicationSource,
    DocType,
)
from app.models.scholarship import Category, PostingStatus, SourceType


# ---------- 공고(Scholarship) ----------
class ScholarshipOut(BaseModel):
    id: int
    title: str
    organization: str | None = None
    source_type: SourceType
    category: Category
    source_platform: str
    source_url: str
    deadline_at: datetime | None = None
    eligibility: dict = Field(default_factory=dict)
    benefit: dict = Field(default_factory=dict)
    required_documents: list[str] = Field(default_factory=list)
    status: PostingStatus

    class Config:
        from_attributes = True


# ---------- 사용자 프로필(매칭 입력) ----------
class UserProfile(BaseModel):
    """매칭 하드필터에 쓰이는 사용자 자격 정보."""

    income_bracket: int | None = Field(default=None, ge=0, le=10)  # 소득분위
    gpa: float | None = Field(default=None, ge=0.0, le=4.5)
    grade_level: str | None = None       # "1".."4"
    region: str | None = None
    major: str | None = None
    interests: list[str] = Field(default_factory=list)


class MatchResult(BaseModel):
    scholarship: ScholarshipOut
    match_score: float
    reasons: list[str] = Field(default_factory=list)  # "소득 3분위 충족" 등


# ---------- 과거/작성 신청서 ----------
class ApplicationDocumentIn(BaseModel):
    doc_type: DocType = DocType.OTHER
    prompt_question: str | None = None
    content_text: str


class ApplicationDocumentOut(ApplicationDocumentIn):
    id: int
    char_count: int
    embedding_status: str

    class Config:
        from_attributes = True


class ApplicationCreate(BaseModel):
    """서비스로 작성한 신청서 저장(플라이휠: source=generated).

    소유자는 세션에서 판단한다. 요청 바디의 user_id는 위조 가능하므로 받지 않는다.
    """

    scholarship_name: str
    organization: str | None = None
    scholarship_id: int | None = None
    source: ApplicationSource = ApplicationSource.GENERATED
    result: ApplicationResult = ApplicationResult.DRAFT
    tags: list[str] = Field(default_factory=list)
    is_reusable: bool = True
    documents: list[ApplicationDocumentIn] = Field(default_factory=list)


class ApplicationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    scholarship_name: str
    organization: str | None = None
    source: ApplicationSource
    result: ApplicationResult
    tags: list[str]
    is_reusable: bool
    documents: list[ApplicationDocumentOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ---------- Q&A ----------
class QARequest(BaseModel):
    user_id: uuid.UUID | None = None
    question: str
    profile: UserProfile | None = None


class QACitation(BaseModel):
    scholarship_id: int
    title: str
    deadline_at: datetime | None = None
    source_url: str


class QAResponse(BaseModel):
    answer: str
    citations: list[QACitation] = Field(default_factory=list)
    grounded: bool = True  # 근거 공고가 있었는지


# ---------- 초안 생성 ----------
class DraftRequest(BaseModel):
    scholarship_id: int
    questions: list[str]  # 새 공고의 문항들


class DraftAnswer(BaseModel):
    question: str
    draft_text: str
    sources: list[str] = Field(default_factory=list)  # 참조한 과거 이력 근거


class DraftResponse(BaseModel):
    scholarship_id: int
    answers: list[DraftAnswer] = Field(default_factory=list)
    used_history: bool = True  # 과거 데이터를 실제로 사용했는지
