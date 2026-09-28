"""공고 목록·상세·매칭 API.

혜택 탭의 기본 진입은 대화가 아니라 **목록**이다. 지금까지는 매칭
엔드포인트만 있어서, 뭐가 올라와 있는지 구경하려면 먼저 소득분위부터
말해야 했다. 목록이 앞에 서고 대화는 초안 생성 도구로 내려간다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.scholarship import Category, PostingStatus, Scholarship
from app.schemas.schemas import MatchResult, UserProfile
from app.services.matching import match_scholarships

router = APIRouter(prefix="/scholarships", tags=["scholarships"])

#: 목록에 기본으로 보이는 상태. NEEDS_REVIEW(파싱 실패)는 사용자에게
#: 보여줄 수 없고, CLOSED 는 신청할 수 없으니 기본에서 뺀다.
_LISTABLE = (PostingStatus.OPEN, PostingStatus.CLOSING_SOON)


class PostingOut(BaseModel):
    id: int
    title: str
    organization: str | None = None
    category: Category
    source_platform: str
    source_url: str
    deadline_at: datetime | None = None
    posted_at: datetime | None = None
    status: PostingStatus
    benefit: dict = {}
    #: 마감까지 남은 일수. 음수면 이미 지났다(목록에서는 안 나온다).
    days_left: int | None = None

    class Config:
        from_attributes = True


class PostingDetailOut(PostingOut):
    eligibility: dict = {}
    required_documents: list[str] = []
    body_text: str = ""


class PostingPage(BaseModel):
    items: list[PostingOut]
    total: int
    offset: int
    limit: int


def _days_left(deadline: datetime | None) -> int | None:
    if deadline is None:
        return None
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    delta = deadline - datetime.now(timezone.utc)
    return delta.days


def _to_out(row: Scholarship, cls=PostingOut):
    out = cls.model_validate(row)
    out.days_left = _days_left(row.deadline_at)
    return out


@router.get("", response_model=PostingPage)
def list_postings(
    category: Category | None = Query(default=None),
    q: str | None = Query(default=None, description="제목·기관 검색어"),
    include_closed: bool = Query(default=False),
    sort: str = Query(default="deadline", pattern="^(deadline|recent)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PostingPage:
    """모집 중인 공고 목록. 기본은 마감 임박순.

    마감 임박순이 기본인 이유: 이 화면이 시간축을 대신한다. 별도 피드 탭
    없이 '오늘 안 챙기면 손해인 것'이 위로 올라와야 한다. 마감일이 없는
    공고(대학 게시판은 마감을 목록에 안 싣는다)는 뒤로 보낸다.
    """
    stmt = select(Scholarship)
    if not include_closed:
        stmt = stmt.where(Scholarship.status.in_(_LISTABLE))
    else:
        stmt = stmt.where(Scholarship.status != PostingStatus.NEEDS_REVIEW)
    if category:
        stmt = stmt.where(Scholarship.category == category)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Scholarship.title.ilike(like), Scholarship.organization.ilike(like))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if sort == "deadline":
        # 마감일 없는 공고를 뒤로. NULL 정렬은 방언마다 달라 표현식으로 못박는다.
        stmt = stmt.order_by(
            (Scholarship.deadline_at.is_(None)).asc(),
            Scholarship.deadline_at.asc(),
            Scholarship.id.desc(),
        )
    else:
        stmt = stmt.order_by(
            (Scholarship.posted_at.is_(None)).asc(),
            Scholarship.posted_at.desc(),
            Scholarship.id.desc(),
        )

    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return PostingPage(
        items=[_to_out(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{posting_id}", response_model=PostingDetailOut)
def get_posting(posting_id: int, db: Session = Depends(get_db)) -> PostingDetailOut:
    """공고 상세. 신청은 source_url 외부 링크로 나간다."""
    row = db.get(Scholarship, posting_id)
    if row is None or row.status == PostingStatus.NEEDS_REVIEW:
        raise HTTPException(404, "공고를 찾을 수 없습니다.")
    return _to_out(row, PostingDetailOut)


@router.post("/match", response_model=list[MatchResult])
def match(
    profile: UserProfile,
    category: Category = Category.SCHOLARSHIP,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[MatchResult]:
    """사용자 프로필 기반 매칭. 하드필터 통과분만 소프트랭킹 정렬."""
    return match_scholarships(db, profile, category=category, limit=limit)
