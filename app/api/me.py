"""마이페이지 API.

사용자의 신청 이력, 저장된 자기소개서(문서), 보유 카드 정보를 조회한다.
로그인 없는 MVP라 user_id를 쿼리로 받는다(프론트는 localStorage 프로필의 user_id 사용).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.models.application import ApplicationDocument, UserApplication
from app.models.card import Card

router = APIRouter(prefix="/me", tags=["me"])


class DocumentOut(BaseModel):
    id: int
    doc_type: str
    prompt_question: str | None = None
    content_text: str
    char_count: int
    created_at: str | None = None


class ApplicationOut(BaseModel):
    id: str
    scholarship_name: str
    organization: str | None = None
    source: str
    result: str
    tags: list[str] = []
    is_reusable: bool
    created_at: str | None = None
    documents: list[DocumentOut] = []


class CardOut(BaseModel):
    id: int
    card_name: str
    issuer: str | None = None


class MyPageOut(BaseModel):
    user_id: str
    applications: list[ApplicationOut]
    documents: list[DocumentOut]      # 재사용 가능한 자기소개서 모음(플랫)
    cards: list[CardOut]
    counts: dict


@router.get("/summary", response_model=MyPageOut)
def my_summary(
    user_id: uuid.UUID,
    card_ids: list[int] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MyPageOut:
    """마이페이지 한 번에 조회: 신청이력 + 자기소개서 + 보유카드.

    card_ids는 온보딩에서 고른 보유 카드 ID(프론트 localStorage). 지정 시
    카드 정보를 함께 반환한다.
    """
    apps = db.scalars(
        select(UserApplication)
        .where(UserApplication.user_id == user_id)
        .options(selectinload(UserApplication.documents))
        .order_by(UserApplication.created_at.desc())
    ).all()

    def _doc_out(d: ApplicationDocument) -> DocumentOut:
        return DocumentOut(
            id=d.id,
            doc_type=d.doc_type.value if hasattr(d.doc_type, "value") else str(d.doc_type),
            prompt_question=d.prompt_question,
            content_text=d.content_text,
            char_count=d.char_count,
            created_at=d.created_at.isoformat() if d.created_at else None,
        )

    applications: list[ApplicationOut] = []
    all_docs: list[DocumentOut] = []
    for a in apps:
        docs = [_doc_out(d) for d in a.documents]
        applications.append(
            ApplicationOut(
                id=str(a.id),
                scholarship_name=a.scholarship_name,
                organization=a.organization,
                source=a.source.value if hasattr(a.source, "value") else str(a.source),
                result=a.result.value if hasattr(a.result, "value") else str(a.result),
                tags=list(a.tags or []),
                is_reusable=a.is_reusable,
                created_at=a.created_at.isoformat() if a.created_at else None,
                documents=docs,
            )
        )
        if a.is_reusable:
            all_docs.extend(docs)

    cards: list[CardOut] = []
    if card_ids:
        rows = db.scalars(select(Card).where(Card.id.in_(card_ids))).all()
        cards = [CardOut(id=c.id, card_name=c.card_name, issuer=c.issuer) for c in rows]

    return MyPageOut(
        user_id=str(user_id),
        applications=applications,
        documents=all_docs,
        cards=cards,
        counts={
            "applications": len(applications),
            "documents": len(all_docs),
            "cards": len(cards),
        },
    )
