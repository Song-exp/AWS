"""온통청년 API 응답 -> RawPosting 매핑."""
from app.crawlers.public import OnjungchoungnyeonCrawler, _regions_from_zip
from app.models.scholarship import Category


def _item(**over):
    base = {
        "plcyNo": "20260909005400213397",
        "plcyNm": "경기 재도전학교",
        "aplyYmd": "20260225 ~ 20260920",
        "frstRegDt": "2026-09-09 13:50:11",
        "zipCd": "41111,41113",
        "sprvsnInstCdNm": "경기도 평생교육과",
        "plcyExplnCn": "재기 지원 프로그램",
    }
    return {**base, **over}


def test_maps_deadline_region_and_unique_url():
    raw = OnjungchoungnyeonCrawler()._to_raw(_item())
    assert raw.deadline_at.strftime("%Y-%m-%d %H:%M") == "2026-09-20 23:59"
    assert raw.eligibility == {"region": ["경기"]}
    assert raw.source_url.endswith("/20260909005400213397")
    assert raw.category == Category.GOV_BENEFIT
    assert "[설명] 재기 지원 프로그램" in raw.body_text


def test_open_ended_scholarship_without_region():
    raw = OnjungchoungnyeonCrawler()._to_raw(
        _item(plcyNm="지역인재 장학금", aplyYmd="", zipCd="")
    )
    assert raw.deadline_at is None and raw.posted_at is not None
    assert raw.eligibility == {}
    assert raw.category == Category.SCHOLARSHIP


def test_apply_period_codes():
    c = OnjungchoungnyeonCrawler()
    always = c._to_raw(_item(aplyPrdSeCd="0057002", aplyYmd="", bizPrdEndYmd="20270228"))
    assert always.deadline_at.strftime("%Y-%m-%d %H:%M") == "2027-02-28 23:59"
    yearly = c._to_raw(_item(aplyPrdSeCd="0057002", aplyYmd="", bizPrdEndYmd="        "))
    assert yearly.deadline_at is None
    assert c._to_raw(_item(aplyPrdSeCd="0057003", aplyYmd="")) is None


def test_regions_and_bad_input():
    prefixes = ("11", "26", "27", "28", "29", "30", "31", "36", "41",
                "43", "44", "46", "47", "48", "50", "51", "52")
    assert _regions_from_zip(",".join(p + "110" for p in prefixes)) == ["전국"]
    # 통합특별시 코드(12xxx): 광주 자치구 / 전남 시군
    assert _regions_from_zip("12270,12760") == ["광주", "전남"]
    merged = ",".join(p + "110" for p in prefixes if p not in ("29", "46"))
    assert _regions_from_zip(merged + ",12210,12110") == ["전국"]
    assert _regions_from_zip("00020220") == []
    assert OnjungchoungnyeonCrawler()._to_raw(_item(plcyNo="")) is None
    assert OnjungchoungnyeonCrawler()._to_raw(_item(aplyYmd="00020220 ~ 20261399")).deadline_at is None
