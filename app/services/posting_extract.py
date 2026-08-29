"""공고 본문(첨부에서 추출한 텍스트) 구조화 서비스.

DeepSeek로 마감일·자격요건·지급액·필수서류·신청문항을 뽑아
Scholarship의 정형 필드(eligibility/benefit/deadline_at 등)를 채운다.
LLM 키가 없으면 규칙기반 폴백으로 최소한의 마감일·지급액만 추출한다.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from app.services import llm

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

_SYSTEM = """너는 장학금 공고문에서 핵심 정보를 구조화하는 도우미다.
주어진 공고 본문을 읽고 아래 JSON 스키마로만 답하라. 설명 문장 없이 JSON만 출력한다.

{
  "deadline": "YYYY-MM-DD 또는 null (신청 마감일. 여러 개면 가장 마지막 접수일)",
  "eligibility": {
     "income_bracket": [해당 소득분위 숫자 배열 또는 []],
     "gpa_min": 최소학점 숫자 또는 null,
     "grade_level": ["대","1","2"...] 또는 [],
     "region": ["지역"] 또는 [],
     "target_desc": "대상 요약 한 문장"
  },
  "benefit": {"amount_krw": 최대 지급액 숫자 또는 null, "amount_desc": "지급액 설명"},
  "required_documents": ["제출서류1", ...],
  "application_questions": ["신청서/자기소개서에서 요구하는 서술 문항", ...]
}

규칙:
- 본문에 없는 값은 null 또는 빈 배열로 둔다. 지어내지 마라.
- application_questions는 '지원동기', '학업계획' 등 서술형 문항만. 없으면 [].
"""

_DATE_RE = re.compile(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})")
_AMOUNT_RE = re.compile(r"(\d[\d,]*)\s*(만원|백만원|천원|원)")


def _fallback_extract(body: str) -> dict:
    """LLM 없이 최소 정보만 추출."""
    result: dict = {"eligibility": {}, "benefit": {}, "required_documents": [], "application_questions": []}
    # 날짜들 중 가장 늦은 것을 마감일 후보로
    dates = []
    for m in _DATE_RE.finditer(body):
        try:
            dates.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=KST))
        except ValueError:
            continue
    if dates:
        result["deadline"] = max(dates).date().isoformat()
    # 금액(만원 단위 위주)
    best = 0
    for m in _AMOUNT_RE.finditer(body):
        num = int(m.group(1).replace(",", ""))
        unit = m.group(2)
        krw = num * (10000 if unit == "만원" else 1_000_000 if unit == "백만원" else 1000 if unit == "천원" else 1)
        best = max(best, krw)
    if best:
        result["benefit"] = {"amount_krw": best, "amount_desc": f"최대 {best:,}원"}
    return result


def _coerce_deadline(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 23, 59, tzinfo=KST)
    except ValueError:
        return None


def extract_structured(body: str) -> dict:
    """공고 본문 -> {deadline_at, eligibility, benefit, required_documents, application_questions}."""
    body = (body or "").strip()
    if len(body) < 30:
        return {}

    if not llm.has_llm():
        data = _fallback_extract(body)
    else:
        try:
            # 본문이 매우 길 수 있으니 앞부분 위주로 전달(핵심 정보가 상단에 몰림)
            raw = llm.chat_complete(_SYSTEM, f"[공고 본문]\n{body[:6000]}", temperature=0.0)
            # JSON 블록만 파싱
            jstart = raw.find("{")
            jend = raw.rfind("}")
            data = json.loads(raw[jstart : jend + 1]) if jstart >= 0 else {}
        except Exception:  # noqa: BLE001
            logger.exception("structured extract failed; fallback")
            data = _fallback_extract(body)

    out: dict = {
        "eligibility": data.get("eligibility") or {},
        "benefit": data.get("benefit") or {},
        "required_documents": data.get("required_documents") or [],
        "application_questions": data.get("application_questions") or [],
    }
    dl = _coerce_deadline(data.get("deadline"))
    if dl:
        out["deadline_at"] = dl
    return out
