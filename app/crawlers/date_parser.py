"""비정형 마감일 표기를 정규화하고, MVP의 '8월 마감' 필터를 적용한다.

한국 공고는 '2026.8.31', '8/31(월) 18:00', '8월 말', '~8.31' 등
표기가 제각각이다. 규칙 기반 파서로 최대한 커버하고, 실패 시 None을
반환해 상위에서 status='needs_review'로 격리하도록 한다.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timezone, timedelta

KST = timezone(timedelta(hours=9))

# 'YYYY.MM.DD', 'YYYY-MM-DD', 'YYYY/MM/DD'
_FULL_DATE = re.compile(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")
# 'MM.DD' 또는 'MM/DD' (연도 생략)
_MONTH_DAY = re.compile(r"(?<!\d)(\d{1,2})[.\-/](\d{1,2})(?!\d)")
# 'HH:MM'
_TIME = re.compile(r"(\d{1,2}):(\d{2})")
# 'N월 말' / 'N월말'
_MONTH_END = re.compile(r"(\d{1,2})\s*월\s*말")


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - timedelta(days=1)).day


def normalize_deadline(text: str, default_year: int = 2026) -> datetime | None:
    """마감일 문자열을 KST tz-aware datetime으로 정규화. 실패 시 None."""
    if not text:
        return None
    text = text.strip()

    # 시간 파싱(없으면 23:59)
    tmatch = _TIME.search(text)
    hh, mm = (int(tmatch.group(1)), int(tmatch.group(2))) if tmatch else (23, 59)
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        hh, mm = 23, 59

    year = month = day = None

    m = _FULL_DATE.search(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        me = _MONTH_END.search(text)
        if me:
            month = int(me.group(1))
            year = default_year
            day = _last_day_of_month(year, month)
        else:
            md = _MONTH_DAY.search(text)
            if md:
                month, day = int(md.group(1)), int(md.group(2))
                year = default_year

    if not (year and month and day):
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None

    try:
        return datetime.combine(date(year, month, day), time(hh, mm), tzinfo=KST)
    except ValueError:
        return None


def is_within_august(dt: datetime | None, year: int = 2026) -> bool:
    """(하위호환) 특정 연-8월 마감 판정. 신규 코드는 is_within_months 사용."""
    return is_within_months(dt, {(year, 8)})


def target_year_months(
    base: date | datetime | None = None, months_ahead: int = 1
) -> set[tuple[int, int]]:
    """기준일의 당월부터 months_ahead 개월 후까지 (연, 월) 집합 반환.

    예) base=2026-08, months_ahead=1 -> {(2026,8),(2026,9)}
        base=2026-12, months_ahead=1 -> {(2026,12),(2027,1)}  # 연 경계 처리
    """
    if base is None:
        base = datetime.now(KST)
    if isinstance(base, datetime):
        base = base.date()

    result: set[tuple[int, int]] = set()
    year, month = base.year, base.month
    for _ in range(months_ahead + 1):
        result.add((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return result


def is_within_months(
    dt: datetime | None, year_months: set[tuple[int, int]]
) -> bool:
    """마감일이 대상 (연, 월) 집합에 속하는지 판정."""
    if dt is None:
        return False
    return (dt.year, dt.month) in year_months
