"""공고/매칭 API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.scholarship import Category
from app.schemas.schemas import MatchResult, UserProfile
from app.services.matching import match_scholarships

router = APIRouter(prefix="/scholarships", tags=["scholarships"])


@router.post("/match", response_model=list[MatchResult])
def match(
    profile: UserProfile,
    category: Category = Category.SCHOLARSHIP,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[MatchResult]:
    """사용자 프로필 기반 매칭. 하드필터 통과분만 소프트랭킹 정렬."""
    return match_scholarships(db, profile, category=category, limit=limit)
