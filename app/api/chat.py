"""챗봇 대화 API + 채팅 중 파일 업로드 + 임베딩 인덱싱 트리거."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user, optional_user, rate_limit_chat, require_admin
from app.models.user import User
from app.models.application import (
    ApplicationDocument,
    ApplicationSource,
    DocType,
    UserApplication,
)
from app.services import chat as chat_service
from app.services import indexing
from app.utils.file_parser import UnsupportedFileType, extract_text

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    # 매 호출이 유료 LLM을 태우므로 분당 상한을 건다.
    dependencies=[Depends(rate_limit_chat)],
)


class ChatMessageRequest(BaseModel):
    session_id: str | None = None
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
def send_message(
    req: ChatMessageRequest,
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    """대화 한 턴 처리. 백엔드가 세션 상태와 LLM 대화를 관리한다.

    로그인은 필수가 아니다. 장학금 탐색은 진입장벽을 낮게 두고, 개인 데이터를
    쓰거나 남기는 지점(첨부 업로드·초안 저장)에서만 로그인을 요구한다.
    """
    reply = chat_service.handle_message(
        db, req.session_id, user.id if user else None, req.message
    )
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
    file: UploadFile = File(...),
    user: User = Depends(current_user),
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

    # 업로드는 로그인 필수이므로 소유자가 항상 정해져 있다.
    sess = chat_service.get_or_create_session(session_id, user.id)
    sess.user_id = user.id

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
index_router = APIRouter(
    prefix="/admin/index",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@index_router.post("/run")
def run_indexing(db: Session = Depends(get_db)) -> dict:
    """pending 문서 + 미인덱싱 공고를 임베딩·적재."""
    return indexing.reindex_all(db)
