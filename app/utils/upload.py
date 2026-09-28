"""업로드 본문 읽기.

`await file.read()` 는 본문을 전부 메모리로 올린 뒤에야 크기를 알 수 있다.
그래서 크기 검사를 나중에 해도 이미 메모리는 다 쓴 상태다. 워커가 1개라
큰 본문 하나로 서비스 전체가 멈춘다. 조금씩 읽고 상한을 넘는 순간 끊는다.
"""
from __future__ import annotations

from fastapi import HTTPException, UploadFile

from app.core.config import settings

_CHUNK = 1024 * 1024


async def read_limited(file: UploadFile, detail: str | None = None) -> bytes:
    """상한(MAX_UPLOAD_MB)까지만 읽는다. 넘으면 413으로 끊는다."""
    limit = settings.max_upload_mb * 1024 * 1024
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(_CHUNK):
        size += len(chunk)
        if size > limit:
            raise HTTPException(
                413,
                detail or f"파일이 너무 큽니다(최대 {settings.max_upload_mb}MB).",
            )
        chunks.append(chunk)
    return b"".join(chunks)
