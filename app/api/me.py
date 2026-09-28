"""마이페이지 API.

사용자의 신청 이력, 저장된 자기소개서(문서), 보유 카드 정보를 조회한다.
대상 사용자는 세션 쿠키에서 판단한다. 예전처럼 user_id를 쿼리로 받으면
UUID만 아는 사람이 남의 자기소개서를 전부 읽을 수 있었다.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import current_user
from app.models.user import User
from app.models.application import ApplicationDocument, DocumentEmbedding, UserApplication
from app.models.card import Card
from app.services import indexing

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


def _doc_out(d: ApplicationDocument) -> DocumentOut:
    return DocumentOut(
        id=d.id,
        doc_type=d.doc_type.value if hasattr(d.doc_type, "value") else str(d.doc_type),
        prompt_question=d.prompt_question,
        content_text=d.content_text,
        char_count=d.char_count,
        created_at=d.created_at.isoformat() if d.created_at else None,
    )


def _app_out(a: UserApplication) -> ApplicationOut:
    return ApplicationOut(
        id=str(a.id),
        scholarship_name=a.scholarship_name,
        organization=a.organization,
        source=a.source.value if hasattr(a.source, "value") else str(a.source),
        result=a.result.value if hasattr(a.result, "value") else str(a.result),
        tags=list(a.tags or []),
        is_reusable=a.is_reusable,
        created_at=a.created_at.isoformat() if a.created_at else None,
        documents=[_doc_out(d) for d in a.documents],
    )


@router.get("/summary", response_model=MyPageOut)
def my_summary(
    card_ids: list[int] | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MyPageOut:
    """마이페이지 한 번에 조회: 신청이력 + 자기소개서 + 보유카드.

    card_ids는 온보딩에서 고른 보유 카드 ID(프론트 localStorage). 지정 시
    카드 정보를 함께 반환한다.
    """
    user_id = user.id
    apps = db.scalars(
        select(UserApplication)
        .where(UserApplication.user_id == user_id)
        .options(selectinload(UserApplication.documents))
        .order_by(UserApplication.created_at.desc())
    ).all()

    applications: list[ApplicationOut] = []
    all_docs: list[DocumentOut] = []
    for a in apps:
        out = _app_out(a)
        applications.append(out)
        if a.is_reusable:
            all_docs.extend(out.documents)

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
            # 자기소개서 1편 = 신청서 1건(문항 답변 묶음). 문항 수가 아니라 편 수를 센다.
            "documents": sum(1 for a in applications if a.is_reusable and a.documents),
            "cards": len(cards),
        },
    )


class DocumentEdit(BaseModel):
    id: int
    content_text: str = Field(max_length=20000)


class ApplicationDocumentsEdit(BaseModel):
    documents: list[DocumentEdit]


@router.put("/applications/{application_id}/documents", response_model=ApplicationOut)
def edit_application_documents(
    application_id: uuid.UUID,
    payload: ApplicationDocumentsEdit,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    """자기소개서 한 편(문항 답변 전부)을 한 번에 고친다.

    저장은 문항 단위로 남긴다. 새 공고의 비슷한 문항에 과거 답변을 찾아
    붙이는 초안 생성이 문항 단위 임베딩을 쓰기 때문이다.
    """
    app_row = db.get(UserApplication, application_id)
    # 남의 신청서와 없는 신청서를 같은 404로 응답해 존재 여부를 흘리지 않는다.
    if app_row is None or app_row.user_id != user.id:
        raise HTTPException(404, "자기소개서를 찾을 수 없습니다.")
    docs = {d.id: d for d in app_row.documents}
    for edit in payload.documents:
        doc = docs.get(edit.id)
        if doc is None:
            raise HTTPException(404, "자기소개서 문항을 찾을 수 없습니다.")
        if doc.content_text == edit.content_text:
            continue
        doc.content_text = edit.content_text
        doc.char_count = len(edit.content_text)
        # 내용이 바뀌면 옛 임베딩은 틀린 근거가 된다. 지우고 다시 색인 대기로 둔다.
        db.query(DocumentEmbedding).filter(DocumentEmbedding.document_id == doc.id).delete()
        doc.embedding_status = "pending"
    db.commit()
    # 고친 내용이 다음 초안의 근거가 되도록 바로 다시 색인한다.
    try:
        indexing.index_documents(db)
    except Exception:  # noqa: BLE001 - 색인 실패가 저장을 막지 않게(pending으로 남아 다음에 처리)
        db.rollback()
    db.refresh(app_row)
    return _app_out(app_row)
