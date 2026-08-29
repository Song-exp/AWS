"""업로드 파일(pdf/docx/hwp)에서 텍스트를 추출한다.

의존성은 함수 내부에서 지연 임포트하여, 특정 포맷 라이브러리가 없어도
모듈 임포트 자체는 실패하지 않게 한다(MVP 스캐폴딩 안정성).
"""
from __future__ import annotations

import os


class UnsupportedFileType(Exception):
    pass


def extract_text(file_path: str) -> str:
    """확장자에 따라 적절한 파서로 라우팅."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext in (".docx",):
        return _extract_docx(file_path)
    if ext in (".hwpx",):
        return _extract_hwpx(file_path)
    if ext in (".hwp",):
        return _extract_hwp(file_path)
    if ext in (".txt",):
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    raise UnsupportedFileType(f"지원하지 않는 파일 형식: {ext}")


def extract_text_from_bytes(content: bytes, filename: str) -> str:
    """메모리상의 파일 바이트에서 텍스트 추출(크롤러가 받은 첨부용).

    파일명 확장자로 형식을 판별한다. HWPX/DOCX는 zip 시그니처(PK)도 함께 확인.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".hwpx":
        return _extract_hwpx_bytes(content)
    if ext == ".docx":
        return _extract_docx_bytes(content)
    if ext == ".pdf":
        return _extract_pdf_bytes(content)
    if ext == ".hwp":
        return _extract_hwp_bytes(content)
    if ext == ".txt":
        return content.decode("utf-8", errors="ignore")
    # 확장자 불명확: zip이면 hwpx로 시도
    if content[:2] == b"PK":
        try:
            return _extract_hwpx_bytes(content)
        except Exception:  # noqa: BLE001
            return ""
    raise UnsupportedFileType(f"지원하지 않는 파일 형식: {ext or '(없음)'}")


def _hwpx_text_from_zip(zf) -> str:
    """열린 zipfile에서 HWPX 본문 텍스트를 추출.

    HWPX는 OWPML(zip) 포맷이다. 본문은 Contents/section*.xml 의 <hp:t>
    태그에 들어 있다(단락 텍스트). 여러 섹션을 순서대로 이어붙인다.
    """
    import re

    sections = sorted(
        n for n in zf.namelist() if re.match(r"Contents/section\d+\.xml", n)
    )
    parts: list[str] = []
    for name in sections:
        raw = zf.read(name).decode("utf-8", errors="ignore")
        for m in re.findall(r"<hp:t>(.*?)</hp:t>", raw, re.S):
            # 태그 잔여물 제거
            txt = re.sub(r"<[^>]+>", "", m)
            if txt.strip():
                parts.append(txt)
    return "\n".join(parts).strip()


def _extract_hwpx(file_path: str) -> str:
    import zipfile

    with zipfile.ZipFile(file_path) as zf:
        return _hwpx_text_from_zip(zf)


def _extract_hwpx_bytes(content: bytes) -> str:
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        return _hwpx_text_from_zip(zf)


def _extract_pdf_bytes(content: bytes) -> str:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n".join((p.extract_text() or "") for p in reader.pages).strip()


def _extract_docx_bytes(content: bytes) -> str:
    import io

    import docx

    document = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs).strip()


def _extract_hwp_bytes(content: bytes) -> str:
    import io

    import olefile

    if not olefile.isOleFile(io.BytesIO(content)):
        return ""
    ole = olefile.OleFileIO(io.BytesIO(content))
    try:
        if ole.exists("PrvText"):
            return ole.openstream("PrvText").read().decode("utf-16-le", errors="ignore").strip()
        return ""
    finally:
        ole.close()


def _extract_pdf(file_path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    parts = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(parts).strip()


def _extract_docx(file_path: str) -> str:
    import docx  # python-docx

    document = docx.Document(file_path)
    return "\n".join(p.text for p in document.paragraphs).strip()


def _extract_hwp(file_path: str) -> str:
    """HWP는 순수 파이썬 지원이 제한적이다.

    한글(HWP) 5.x는 OLE 복합문서로, 'PrvText' 스트림에 미리보기 텍스트가
    UTF-16LE로 저장되어 있어 이를 우선 추출한다. 완전한 본문 추출은
    후속 개선 대상(예: hwp5 CLI 연동)으로 남긴다.
    """
    import olefile

    if not olefile.isOleFile(file_path):
        raise UnsupportedFileType("유효한 HWP(OLE) 파일이 아닙니다.")

    ole = olefile.OleFileIO(file_path)
    try:
        if ole.exists("PrvText"):
            data = ole.openstream("PrvText").read()
            return data.decode("utf-16-le", errors="ignore").strip()
        return ""  # 본문 추출은 후속 개선
    finally:
        ole.close()
