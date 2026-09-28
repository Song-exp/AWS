"""마감일 정규화: 기간 표기는 끝 날짜, 잘린 기간은 알 수 없음."""
from datetime import datetime

from app.crawlers.date_parser import KST, normalize_deadline


def test_range_uses_end_date():
    dl = normalize_deadline("2026.9.1.(월) ~ 2026.9.30.(화) 18:00")
    assert dl.strftime("%Y-%m-%d %H:%M") == "2026-09-30 18:00"
    assert normalize_deadline("(~9.16 수)2026년 2학기 국가장학금").strftime("%m-%d") == "09-16"


def test_truncated_range_is_unknown():
    assert normalize_deadline("부정수급 자진신고 캠페인 안내(2026.8.10.(월) ~") is None


def test_month_day_defaults_to_current_year():
    assert normalize_deadline("마감 3/15").year == datetime.now(KST).year
