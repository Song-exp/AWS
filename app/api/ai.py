"""Q&A + 초안 생성 API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.schemas import DraftRequest, DraftResponse, QARequest, QAResponse
from app.services import rag

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/qa", response_model=QAResponse)
def qa(req: QARequest, db: Session = Depends(get_db)) -> QAResponse:
    """근거 기반(Q&A) 응답. 근거 공고 없으면 grounded=False."""
    return rag.answer_question(db, req)


@router.post("/draft", response_model=DraftResponse)
def draft(req: DraftRequest, db: Session = Depends(get_db)) -> DraftResponse:
    """과거 신청 이력 기반 초안 생성. 이력 없으면 used_history=False."""
    return rag.generate_draft(db, req.user_id, req.scholarship_id, req.questions)
