"""챗봇 대화 API + 채팅 중 파일 업로드 + 임베딩 인덱싱 트리거."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.application import (
    ApplicationDocument,
    ApplicationSource,
    DocType,
    UserApplication,
)
from app.services import chat as chat_service
from app.services import indexing
from app.utils.file_parser import UnsupportedFileType, extract_text

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    session_id: str | None = None
    user_id: uuid.UUID | None = None
    message: str


class CandidateOut(BaseModel):
    index: int
    id: int
    title: str
    deadline: str | None = None
    reasons: list[str] = []


class ChatMessageResponse(BaseModel):
    session_id: str
    state: str
    message: str
    candidates: list[CandidateOut] = []
    draft: dict | None = None
    profile: dict = {}


@router.post("/message", response_model=ChatMessageResponse)
def send_message(req: ChatMessageRequest, db: Session = Depends(get_db)) -> ChatMessageResponse:
    """대화 한 턴 처리. 백엔드가 세션 상태와 LLM 대화를 관리한다."""
    reply = chat_service.handle_message(db, req.session_id, req.user_id, req.message)
    return ChatMessageResponse(
        session_id=reply.session_id,
        state=reply.state,
        message=reply.message,
        candidates=[CandidateOut(**c) for c in reply.candidates],
        draft=reply.draft,
        profile=reply.profile,
    )


@router.post("/upload", response_model=ChatMessageResponse)
async def upload_in_chat(
    session_id: str | None = Form(default=None),
    user_id: uuid.UUID | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    """대화 중 과거 신청서(PDF/DOCX/HWP/TXT)를 첨부한다.

    텍스트를 추출해 사용자 이력으로 저장하고, 임베딩 인덱싱까지 수행한다.
    이후 초안 생성 시 이 내용이 근거로 쓰인다(플라이휠).
    """
    os.makedirs(settings.upload_dir, exist_ok=True)
    original = os.path.basename(file.filename or "upload")
    safe_name = f"{uuid.uuid4().hex}_{original}"
    dest = os.path.join(settings.upload_dir, safe_name)

    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"파일이 너무 큽니다(최대 {settings.max_upload_mb}MB).")
    with open(dest, "wb") as f:
        f.write(content)

    try:
        text = extract_text(dest)
    except UnsupportedFileType as e:
        raise HTTPException(status_code=415, detail=str(e))

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="파일에서 텍스트를 추출하지 못했습니다. 이미지로만 된 PDF일 수 있어요.",
        )

    # 세션에 사용자 ID가 없으면 새로 부여(로그인 없는 MVP)
    sess = chat_service.get_or_create_session(session_id, user_id)
    if sess.user_id is None:
        sess.user_id = user_id or uuid.uuid4()

    app_row = UserApplication(
        user_id=sess.user_id,
        scholarship_name=f"첨부: {original}",
        source=ApplicationSource.UPLOADED,
        source_file_path=dest,
        is_reusable=True,
    )
    app_row.documents.append(
        ApplicationDocument(
            doc_type=DocType.OTHER,
            prompt_question=None,
            content_text=text,
            char_count=len(text),
        )
    )
    db.add(app_row)
    db.commit()

    # 업로드 즉시 인덱싱해 초안 생성에 바로 활용되게 한다
    try:
        indexing.index_documents(db)
    except Exception:  # noqa: BLE001 - 인덱싱 실패가 업로드를 막지 않게
        pass

    reply = chat_service.note_upload(db, sess.session_id, sess.user_id, original, len(text))
    return ChatMessageResponse(
        session_id=reply.session_id,
        state=reply.state,
        message=reply.message,
        candidates=[],
        draft=None,
        profile=reply.profile,
    )


# --- 인덱싱 트리거(운영/배치) ---
index_router = APIRouter(prefix="/admin/index", tags=["admin"])


@index_router.post("/run")
def run_indexing(db: Session = Depends(get_db)) -> dict:
    """pending 문서 + 미인덱싱 공고를 임베딩·적재."""
    return indexing.reindex_all(db)
