"""신청서 이력 API: 파일 업로드(과거 이력) + 서비스 작성분 저장(플라이휠)."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user
from app.models.user import User
from app.models.application import (
    ApplicationDocument,
    ApplicationSource,
    DocType,
    UserApplication,
)
from app.schemas.schemas import ApplicationCreate, ApplicationOut
from app.utils.file_parser import UnsupportedFileType, extract_text
from app.utils.upload import read_limited

# 전부 개인 데이터다. 라우터 수준에서 로그인을 강제한다.
router = APIRouter(
    prefix="/applications",
    tags=["applications"],
    dependencies=[Depends(current_user)],
)


@router.post("/upload", response_model=ApplicationOut)
async def upload_application(
    scholarship_name: str = Form(...),
    organization: str | None = Form(default=None),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    """과거 신청서 파일 업로드 -> 텍스트 추출 -> 이력 저장(source=uploaded)."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename or 'upload')}"
    dest = os.path.join(settings.upload_dir, safe_name)

    content = await read_limited(file)
    with open(dest, "wb") as f:
        f.write(content)

    try:
        text = extract_text(dest)
    except UnsupportedFileType as e:
        os.remove(dest)  # 거절한 파일을 디스크에 남기지 않는다
        raise HTTPException(status_code=415, detail=str(e))

    app_row = UserApplication(
        user_id=user.id,
        scholarship_name=scholarship_name,
        organization=organization,
        source=ApplicationSource.UPLOADED,
        source_file_path=dest,
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
    db.refresh(app_row)
    return ApplicationOut.model_validate(app_row)


@router.post("", response_model=ApplicationOut)
def create_application(
    payload: ApplicationCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApplicationOut:
    """서비스로 작성한 신청서 저장. source=generated로 축적되어 다음 초안의 소스가 된다(플라이휠)."""
    app_row = UserApplication(
        user_id=user.id,
        scholarship_name=payload.scholarship_name,
        organization=payload.organization,
        scholarship_id=payload.scholarship_id,
        source=payload.source,
        result=payload.result,
        tags=payload.tags,
        is_reusable=payload.is_reusable,
    )
    for doc in payload.documents:
        app_row.documents.append(
            ApplicationDocument(
                doc_type=doc.doc_type,
                prompt_question=doc.prompt_question,
                content_text=doc.content_text,
                char_count=len(doc.content_text),
            )
        )
    db.add(app_row)
    db.commit()
    db.refresh(app_row)
    return ApplicationOut.model_validate(app_row)


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationOut]:
    rows = db.scalars(
        select(UserApplication).where(UserApplication.user_id == user.id)
    ).all()
    return [ApplicationOut.model_validate(r) for r in rows]


@router.delete("/{application_id}", status_code=204, response_class=Response)
def delete_application(
    application_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    row = db.get(UserApplication, application_id)
    # 남의 것을 지우지 못하게 소유자를 확인한다. 존재 여부를 알려주지 않도록
    # '없음'과 '내 것이 아님'을 똑같이 404로 응답한다.
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="신청서를 찾을 수 없습니다.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
