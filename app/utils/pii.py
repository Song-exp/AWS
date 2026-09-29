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


#: 주민등록번호. 위 _PATTERNS 의 것은 하이픈을 요구해서 '9901011234567' 처럼
#: 붙여 쓴 13자리를 놓친다(학번 패턴도 8~10자리라 걸리지 않는다). 저장 자체를
#: 막아야 하는 값이라 여기서는 더 촘촘히 본다.
#: 앞 6자리가 생년월일(월 01~12, 일 01~31), 뒤 7자리의 첫 자리가 성별·국적
#: 코드(1~8)인지 확인한다. 이 구조를 보지 않으면 계좌번호·인증번호까지
#: 지워져 초안의 근거가 망가진다.
_RRN_STRICT = re.compile(
    r"(?<![0-9])"
    r"\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])"
    r"[-\s]?"
    r"[1-8]\d{6}"
    r"(?![0-9])"
)


def mask_pii(text: str) -> str:
    """알려진 PII 패턴을 플레이스홀더로 치환."""
    masked = text
    for pattern, placeholder in _PATTERNS:
        masked = pattern.sub(placeholder, masked)
    return masked


def strip_rrn(text: str) -> str:
    """주민등록번호를 지운 문자열을 돌려준다.

    주민등록번호는 법령 근거가 있어야 처리할 수 있고 이용자 동의로는 갈음할 수
    없다. 이 서비스는 그 근거가 없으므로 **저장하지 않는다.** 물어보지도 않지만,
    이용자가 올린 과거 신청서 안에 들어 있을 수 있어 저장 직전에 지운다.
    """
    if not text:
        return text
    return _RRN_STRICT.sub("[RRN]", text)
