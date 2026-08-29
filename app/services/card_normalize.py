"""카드 혜택 데이터 정규화 유틸.

원본 JSON의 표기가 제각각이라 지도 매장(stores.brand)과 조인하려면
정규화가 필요하다.

- merchant_raw -> brand_key 목록 (복합 가맹점 분리)
- '5~20' 같은 범위 문자열 -> (min, max)
- period_type -> 실제 valid_from/valid_to
- '건당 1,000엔(JPY)' -> 통화 구분 + 숫자
"""
from __future__ import annotations

import re
from datetime import date

# 지도에 존재하는(또는 존재할 수 있는) 브랜드 표준 키.
# stores.brand 값과 일치해야 조인된다. '이마트24 생협'처럼 접미어가 붙은
# 매장도 매칭되도록 prefix 매칭을 병행한다.
KNOWN_BRANDS = [
    "CU",
    "GS25",
    "세븐일레븐",
    "이마트24",
    "GS더프레시",
    "이마트",
    "이마트 에브리데이",
    "홈플러스",
    "홈플러스 익스프레스",
    "롯데슈퍼",
    "롯데마트",
    "농협 하나로마트",
    "스타벅스",
    "메가MGC커피",
    "파리바게뜨",
    "뚜레쥬르",
    "아웃백",
    "VIPS",
    "올리브영",
    "컬리",
]

# 원본 표기 -> 표준 브랜드 키 목록.
# 복합 가맹점은 여러 브랜드로 분리하고, 지도와 무관한 항목은 빈 리스트로 제외한다.
_MERCHANT_MAP: dict[str, list[str]] = {
    "CU": ["CU"],
    "GS25": ["GS25"],
    "세븐일레븐": ["세븐일레븐"],
    "이마트24": ["이마트24"],
    "GS25 / GS더프레시": ["GS25", "GS더프레시"],
    "GS25·GS더프레시": ["GS25", "GS더프레시"],
    "이마트": ["이마트"],
    "이마트 에브리데이": ["이마트 에브리데이"],
    "홈플러스": ["홈플러스"],
    "홈플러스 익스프레스": ["홈플러스 익스프레스"],
    "롯데슈퍼": ["롯데슈퍼"],
    "농협 하나로마트": ["농협 하나로마트"],
    "이마트/하나로마트/롯데마트/GS THE FRESH": [
        "이마트",
        "농협 하나로마트",
        "롯데마트",
        "GS더프레시",
    ],
    "스타벅스": ["스타벅스"],
    "메가MGC커피": ["메가MGC커피"],
    "파리바게뜨": ["파리바게뜨"],
    "뚜레쥬르": ["뚜레쥬르"],
    "아웃백": ["아웃백"],
    "VIPS": ["VIPS"],
    "아웃백·VIPS": ["아웃백", "VIPS"],
    "올리브영": ["올리브영"],
    "컬리": ["컬리"],
    # --- 지도 매칭 대상이 아닌 항목(군마트/해외/불특정) ---
    "PX(군마트)": [],
    "PX·GS25 해군마트": [],
    "GS25 해군마트": [],
    "세븐일레븐/로손/패밀리마트(일본)": [],
    "세븐일레븐(일본)": [],
    "로손": [],
    "패밀리마트": [],
    "국내외 전 가맹점": [],
    "(미확인)": [],
    "음식점 등(점심·저녁 특정 시간)": [],
    "포천힐스CC 주변맛집": [],
    "소피텔 서울 식음업장": [],
    "데일리샷": [],
    "패스트푸드": [],
}

_RANGE_RE = re.compile(r"^\s*([\d.]+)\s*[~\-–]\s*([\d.]+)\s*$")
_NUM_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def normalize_merchant(merchant_raw: str) -> list[str]:
    """가맹점 원본 표기를 표준 브랜드 키 목록으로 변환.

    매핑에 없으면 KNOWN_BRANDS 중 포함관계로 추정하고, 그래도 없으면
    빈 리스트(지도 매칭 제외)를 반환한다.
    """
    if merchant_raw is None:
        return []
    raw = merchant_raw.strip()
    if raw in _MERCHANT_MAP:
        return _MERCHANT_MAP[raw]

    # 해외/군마트 등 매칭 제외 신호
    if any(k in raw for k in ("일본", "군마트", "PX", "해군", "미확인", "전 가맹점")):
        return []

    # 구분자로 분리 후 각 토큰을 알려진 브랜드와 대조
    tokens = re.split(r"[/·,]| 및 ", raw)
    found: list[str] = []
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        for b in KNOWN_BRANDS:
            if t == b or b in t:
                if b not in found:
                    found.append(b)
                break
    return found


def parse_benefit_value(value) -> tuple[float | None, float | None]:
    """benefit_value를 (min, max)로 변환. '5~20' -> (5,20), 20 -> (20,20)."""
    if value is None:
        return (None, None)
    if isinstance(value, (int, float)):
        return (float(value), float(value))
    s = str(value).strip()
    m = _RANGE_RE.match(s)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    nums = _NUM_RE.findall(s)
    if not nums:
        return (None, None)
    v = float(nums[0].replace(",", ""))
    return (v, v)


def parse_min_payment(raw) -> tuple[int | None, str | None]:
    """최소 결제금액 파싱. 원화만 숫자로 변환하고 원문을 함께 보관.

    '5000' -> (5000, '5000'), '건당 1,000엔(JPY)' -> (None, 원문)
    """
    if raw is None:
        return (None, None)
    if isinstance(raw, (int, float)):
        return (int(raw), str(raw))
    s = str(raw).strip()
    if not s:
        return (None, None)
    # 외화 표기는 원화 금액으로 쓰지 않는다
    if any(k in s for k in ("엔", "JPY", "달러", "USD")):
        return (None, s)
    nums = _NUM_RE.findall(s)
    if not nums:
        return (None, s)
    return (int(float(nums[0].replace(",", ""))), s)


def period_to_dates(period_type: str | None, period_text: str | None = None) -> tuple[date | None, date | None]:
    """period_type을 실제 기간으로 변환(2026년 8월 기준 데이터).

    always_on  -> (None, None)  무기한
    monthly_aug-> 2026-08-01 ~ 2026-08-31
    week4_aug  -> 2026-08-20 ~ 2026-08-31
    """
    # period 원문에 'YYYY-MM-DD ~ YYYY-MM-DD'가 있으면 그걸 우선 사용
    if period_text:
        found = re.findall(r"(\d{4})-(\d{2})-(\d{2})", period_text)
        if len(found) >= 2:
            a = date(int(found[0][0]), int(found[0][1]), int(found[0][2]))
            b = date(int(found[1][0]), int(found[1][1]), int(found[1][2]))
            return (a, b)

    if period_type == "monthly_aug":
        return (date(2026, 8, 1), date(2026, 8, 31))
    if period_type == "week4_aug":
        return (date(2026, 8, 20), date(2026, 8, 31))
    return (None, None)


def detect_excludes_simple_pay(conditions: list[str] | None) -> bool:
    """'간편결제 제외' 류 조건이 있으면 True."""
    if not conditions:
        return False
    joined = " ".join(conditions)
    return "간편결제 제외" in joined or "간편결제 국내 이용 제외" in joined


# 매장 브랜드(stores.brand) -> 표준 브랜드 키.
# '이마트24 생협'처럼 접미어가 붙은 실제 매장명을 정규화한다.
# 주의: '이마트24'와 '이마트'는 다른 브랜드이므로 단순 prefix 비교를 쓰면
# 대형마트 혜택이 편의점에 잘못 붙는다. 긴 이름을 먼저 확인한다.
_STORE_BRAND_ALIASES = [
    ("이마트24", "이마트24"),          # 반드시 '이마트'보다 먼저
    ("이마트 에브리데이", "이마트 에브리데이"),
    ("이마트", "이마트"),
    ("홈플러스 익스프레스", "홈플러스 익스프레스"),
    ("홈플러스", "홈플러스"),
    ("GS더프레시", "GS더프레시"),
    ("GS25", "GS25"),
    ("세븐일레븐", "세븐일레븐"),
    ("CU", "CU"),
    ("롯데슈퍼", "롯데슈퍼"),
    ("롯데마트", "롯데마트"),
    ("농협 하나로마트", "농협 하나로마트"),
    ("스타벅스", "스타벅스"),
    ("메가MGC커피", "메가MGC커피"),
    ("파리바게뜨", "파리바게뜨"),
    ("뚜레쥬르", "뚜레쥬르"),
    ("아웃백", "아웃백"),
    ("VIPS", "VIPS"),
    ("올리브영", "올리브영"),
]


def store_brand_key(store_brand: str | None) -> str | None:
    """매장 브랜드명을 카드혜택 조인용 표준 키로 변환.

    '이마트24 생협' -> '이마트24' / 'GS25' -> 'GS25'
    """
    if not store_brand:
        return None
    s = store_brand.strip()
    for needle, key in _STORE_BRAND_ALIASES:
        if s.startswith(needle) or s == needle:
            return key
    return s
