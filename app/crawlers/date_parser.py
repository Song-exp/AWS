"""비정형 마감일 표기를 정규화한다.

한국 공고는 '2026.8.31', '8/31(월) 18:00', '8월 말', '~8.31' 등
표기가 제각각이다. 규칙 기반 파서로 최대한 커버하고, 실패 시 None을
반환한다(상위 파이프라인의 '마감일 없는 공고' 규칙을 따른다).
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


def normalize_deadline(text: str, default_year: int | None = None) -> datetime | None:
    """마감일 문자열을 KST tz-aware datetime으로 정규화. 실패 시 None."""
    if not text:
        return None
    text = text.strip()
    # 기간 표기('9.1 ~ 9.30')면 끝 날짜만 본다. 끝이 잘렸으면('8.10 ~') 알 수 없다.
    if "~" in text:
        text = text.rsplit("~", 1)[1]
    if default_year is None:
        default_year = datetime.now(KST).year

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
