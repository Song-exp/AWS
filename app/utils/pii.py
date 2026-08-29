"""임베딩/저장 전 개인식별정보(PII) 마스킹.

과거 신청서에는 이름·학번·연락처·주민번호 등이 섞일 수 있어,
벡터 인덱싱 전에 마스킹하여 민감정보 노출을 줄인다.
"""
from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 주민등록번호 (6자리-7자리)
    (re.compile(r"\b\d{6}-\d{7}\b"), "[RRN]"),
    # 휴대폰 번호
    (re.compile(r"\b01[016-9]-?\d{3,4}-?\d{4}\b"), "[PHONE]"),
    # 이메일
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    # 학번(8~10자리 숫자 단독) - 과탐지 방지 위해 경계 엄격
    (re.compile(r"\b\d{8,10}\b"), "[STUDENT_ID]"),
]


def mask_pii(text: str) -> str:
    """알려진 PII 패턴을 플레이스홀더로 치환."""
    masked = text
    for pattern, placeholder in _PATTERNS:
        masked = pattern.sub(placeholder, masked)
    return masked
