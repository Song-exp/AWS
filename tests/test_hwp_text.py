"""HWP 5.x 본문 레코드 파싱(PrvText 미리보기가 잘리는 문제 대응)."""
import struct

from app.utils.file_parser import _hwp_section_text


def _record(tag: int, payload: bytes) -> bytes:
    return struct.pack("<I", tag | (len(payload) << 20)) + payload


def test_section_text_reads_paragraphs_and_skips_controls():
    table_ctrl = struct.pack("<H", 11) + b"\x00" * 14  # 8 wchar 확장 제어(표)
    para = (
        "신청기간".encode("utf-16-le") + table_ctrl
        + " ~ 9.30".encode("utf-16-le") + struct.pack("<H", 13)
    )
    data = (
        _record(66, b"\x00" * 8)  # PARA_HEADER: 텍스트 아님
        + _record(67, para)
        + _record(67, "둘째 문단".encode("utf-16-le"))
    )
    assert _hwp_section_text(data) == "신청기간 ~ 9.30\n둘째 문단"


def test_section_text_handles_extended_size():
    long_text = ("가" * 5000).encode("utf-16-le")  # 12비트 크기(4095) 초과
    data = struct.pack("<I", 67 | (0xFFF << 20)) + struct.pack("<I", len(long_text)) + long_text
    assert _hwp_section_text(data) == "가" * 5000
