"""업로드 파일(pdf/docx/hwp)에서 텍스트를 추출한다.

의존성은 함수 내부에서 지연 임포트하여, 특정 포맷 라이브러리가 없어도
모듈 임포트 자체는 실패하지 않게 한다(MVP 스캐폴딩 안정성).
"""
from __future__ import annotations

import os


class UnsupportedFileType(Exception):
    pass


#: 압축을 풀었을 때 허용하는 최대 크기. hwpx·docx 는 zip 이라 10MB 파일이 수 GB로
#: 부풀 수 있다(압축 폭탄). 그러면 워커가 메모리 부족으로 죽어 서비스가 멈춘다.
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024


def _guard_zip_size(zf) -> None:
    """압축을 풀기 전에 원본 크기 합계를 먼저 본다."""
    total = sum(info.file_size for info in zf.infolist())
    if total > MAX_UNCOMPRESSED_BYTES:
        raise UnsupportedFileType(
            f"파일이 너무 큽니다(압축을 풀면 {total // (1024 * 1024)}MB). "
            "내용을 줄여 다시 올려주세요."
        )


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
        _guard_zip_size(zf)
        return _hwpx_text_from_zip(zf)


def _extract_hwpx_bytes(content: bytes) -> str:
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        _guard_zip_size(zf)
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
        return _hwp_text(ole)
    finally:
        ole.close()


#: HWP 레코드 태그: 문단 텍스트
_HWPTAG_PARA_TEXT = 67
#: 8 wchar를 차지하는 인라인·확장 제어문자(탭·표·그림 등). 나머지 0~31은 1 wchar.
_HWP_WIDE_CTRL = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}


def _hwp_para_text(buf: bytes) -> str:
    """PARA_TEXT 레코드(UTF-16LE) -> 문자열. 제어문자는 건너뛰거나 공백으로 바꾼다."""
    import struct

    out = bytearray()
    i, end = 0, len(buf) - len(buf) % 2
    while i < end:
        (ch,) = struct.unpack_from("<H", buf, i)
        if ch >= 32:
            out += buf[i:i + 2]
            i += 2
        elif ch in _HWP_WIDE_CTRL:
            if ch == 9:
                out += "\t".encode("utf-16-le")
            i += 16
        else:
            out += ("\n" if ch in (10, 13) else " ").encode("utf-16-le")
            i += 2
    return out.decode("utf-16-le", errors="ignore")


def _hwp_section_text(data: bytes) -> str:
    """압축 해제된 BodyText/SectionN 스트림에서 문단 텍스트를 모은다.

    레코드 헤더(uint32): 태그 10비트 | 레벨 10비트 | 크기 12비트(0xFFF면 다음 uint32).
    """
    import struct

    paras: list[str] = []
    pos = 0
    while pos + 4 <= len(data):
        (header,) = struct.unpack_from("<I", data, pos)
        pos += 4
        tag, size = header & 0x3FF, header >> 20
        if size == 0xFFF:
            (size,) = struct.unpack_from("<I", data, pos)
            pos += 4
        if tag == _HWPTAG_PARA_TEXT:
            text = _hwp_para_text(data[pos:pos + size]).strip()
            if text:
                paras.append(text)
        pos += size
    return "\n".join(paras)


def _hwp_text(ole) -> str:
    """HWP 5.x 본문 텍스트. 읽지 못하면 PrvText(미리보기)로 폴백한다.

    PrvText는 앞부분 약 1,000자에서 잘려 뒤쪽의 마감일·자격이 빠진다.
    배포용 문서(ViewText, 암호화)는 본문을 못 읽으므로 미리보기만 남는다.
    """
    import struct
    import zlib

    try:
        props = struct.unpack_from("<I", ole.openstream("FileHeader").read(), 36)[0]
        sections = sorted(
            (e for e in ole.listdir() if len(e) == 2 and e[0] == "BodyText"),
            key=lambda e: int(e[1].removeprefix("Section")),
        )
        parts = []
        for entry in sections:
            data = ole.openstream(entry).read()
            if props & 1:  # 압축 문서
                data = zlib.decompress(data, -15)
            parts.append(_hwp_section_text(data))
        text = "\n".join(p for p in parts if p).strip()
    except Exception:  # noqa: BLE001 - 구조가 예상과 다르면 미리보기로 폴백
        text = ""
    if text:
        return text
    if ole.exists("PrvText"):
        return ole.openstream("PrvText").read().decode("utf-16-le", errors="ignore").strip()
    return ""


def _extract_pdf(file_path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    parts = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(parts).strip()


def _extract_docx(file_path: str) -> str:
    import zipfile

    import docx  # python-docx

    # docx 도 zip 이다. python-docx 에 넘기기 전에 크기를 먼저 본다.
    with zipfile.ZipFile(file_path) as zf:
        _guard_zip_size(zf)

    document = docx.Document(file_path)
    return "\n".join(p.text for p in document.paragraphs).strip()


def _extract_hwp(file_path: str) -> str:
    """한글(HWP) 5.x는 OLE 복합문서다. 본문 레코드를 직접 읽는다(_hwp_text)."""
    import olefile

    if not olefile.isOleFile(file_path):
        raise UnsupportedFileType("유효한 HWP(OLE) 파일이 아닙니다.")

    ole = olefile.OleFileIO(file_path)
    try:
        return _hwp_text(ole)
    finally:
        ole.close()
