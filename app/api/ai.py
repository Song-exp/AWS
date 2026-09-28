"""Q&A + 초안 생성 API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, rate_limit_chat
from app.models.user import User
from app.schemas.schemas import DraftRequest, DraftResponse, QARequest, QAResponse
from app.services import rag

# 두 엔드포인트 모두 외부 LLM을 호출한다. 로그인과 호출 상한을 라우터 단위로
# 건다. 빠뜨리면 계정 없는 사람이 LLM 비용을 무한히 쓰고, 호출이 워커를
# 점유해 서비스가 멈춘다(워커는 1개다).
router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(current_user), Depends(rate_limit_chat)],
)


@router.post("/qa", response_model=QAResponse)
def qa(req: QARequest, db: Session = Depends(get_db)) -> QAResponse:
    """근거 기반(Q&A) 응답. 근거 공고 없으면 grounded=False."""
    return rag.answer_question(db, req)


@router.post("/draft", response_model=DraftResponse)
def draft(
    req: DraftRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> DraftResponse:
    """과거 신청 이력 기반 초안 생성. 이력 없으면 used_history=False.

    이력은 본인 것만 근거로 쓴다. user_id를 요청에서 받으면 남의 자기소개서가
    내 초안에 섞여 나온다.
    """
    return rag.generate_draft(db, user.id, req.scholarship_id, req.questions)
