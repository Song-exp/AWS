"""샘플 장학금 공고 시드(개발/데모용).

실제 공고 API(청년정책 등) 연결 전까지 챗봇 매칭·초안·아카이빙 흐름을
끝까지 확인하기 위한 데이터다.

기준 시점은 **2026년 8월**(카드 혜택 데이터 as_of 2026-08-28과 동일)이며,
마감일은 8월 말 ~ 9월 초에 분포시켜 '당월+익월' 수집 범위와 마감임박
정렬을 함께 확인할 수 있게 했다.

실데이터와 구분하려고 다음을 지킨다:
  - source_platform = "sample"
  - content_key 접두어 "sample:"

실데이터 연결 후에는 아래로 지울 수 있다:
    python -m app.scripts.seed_sample_scholarships --clear
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select

from app.core.db import SessionLocal, init_db
from app.models.scholarship import (
    Category,
    PostingStatus,
    Scholarship,
    SourceType,
)

KST = timezone(timedelta(hours=9))
SAMPLE_PLATFORM = "sample"

# 데이터 기준 시점(2026년 8월)
AS_OF = date(2026, 8, 28)


def _dl(year: int, month: int, day: int, hour: int = 18) -> datetime:
    """마감일시(KST)."""
    return datetime.combine(date(year, month, day), time(hour, 0), tzinfo=KST)


# 소득분위·학점·지역 조합을 다양하게 두어 매칭 로직을 확인할 수 있게 구성.
# deadline은 2026년 8월 기준(당월 말 ~ 익월 초)으로 고정한다.
_SAMPLES: list[dict] = [
    {
        "title": "2026-2학기 국가장학금 II유형(대학 연계)",
        "organization": "한국장학재단",
        "deadline": _dl(2026, 8, 31),
        "eligibility": {"income_bracket": [1, 2, 3, 4, 5, 6, 7, 8], "gpa_min": 3.0, "region": ["전국"]},
        "benefit": {"type": "tuition", "amount_krw": 3_500_000, "amount_desc": "등록금 최대 350만원"},
        "required_documents": ["가족관계증명서", "성적증명서"],
        "body": "소득구간 8분위 이하 재학생 대상 등록금 지원. 직전학기 12학점 이상 이수 및 평점 3.0 이상.",
    },
    {
        "title": "저소득층 생활비 장학금(주거·식비 지원)",
        "organization": "교육부",
        "deadline": _dl(2026, 8, 29),
        "eligibility": {"income_bracket": [1, 2, 3, 4], "gpa_min": 2.5, "region": ["전국"]},
        "benefit": {"type": "living", "amount_krw": 1_200_000, "amount_desc": "학기당 생활비 120만원"},
        "required_documents": ["소득분위 확인서", "통장사본"],
        "body": "소득 4분위 이하 학생의 생활비를 지원한다. 평점 2.5 이상이면 신청 가능.",
    },
    {
        "title": "서울시 대학생 학업장려 장학금",
        "organization": "서울시",
        "deadline": _dl(2026, 8, 31),
        "eligibility": {"income_bracket": [1, 2, 3, 4, 5, 6], "gpa_min": 3.3, "region": ["서울"]},
        "benefit": {"type": "tuition", "amount_krw": 2_000_000, "amount_desc": "등록금 200만원"},
        "required_documents": ["주민등록초본", "성적증명서", "자기소개서"],
        "body": "서울 거주 대학생 대상. 소득 6분위 이하, 평점 3.3 이상. 자기소개서 제출 필수.",
    },
    {
        "title": "이공계 우수인재 장학금",
        "organization": "과학기술정보통신부",
        "deadline": _dl(2026, 9, 10),
        "eligibility": {
            "income_bracket": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "gpa_min": 3.5,
            "region": ["전국"],
            "major": ["공학", "이공계", "컴퓨터"],
        },
        "benefit": {"type": "both", "amount_krw": 4_000_000, "amount_desc": "등록금 전액 + 학업장려금"},
        "required_documents": ["성적증명서", "학업계획서", "추천서"],
        "body": "이공계 전공 재학생 중 평점 3.5 이상. 소득 무관. 학업계획서와 추천서 필요.",
    },
    {
        "title": "다문화·한부모 가정 대학생 지원 장학금",
        "organization": "여성가족부",
        "deadline": _dl(2026, 8, 30),
        "eligibility": {"income_bracket": [1, 2, 3, 4, 5], "region": ["전국"]},
        "benefit": {"type": "living", "amount_krw": 1_500_000, "amount_desc": "생활비 150만원"},
        "required_documents": ["가족관계증명서", "재학증명서"],
        "body": "다문화 또는 한부모 가정 대학생 대상 생활비 지원. 학점 제한 없음.",
    },
    {
        "title": "지역인재 육성 장학금(경기)",
        "organization": "경기도인재육성재단",
        "deadline": _dl(2026, 9, 4),
        "eligibility": {"income_bracket": [1, 2, 3, 4, 5, 6, 7], "gpa_min": 3.0, "region": ["경기"]},
        "benefit": {"type": "tuition", "amount_krw": 2_500_000, "amount_desc": "등록금 250만원"},
        "required_documents": ["주민등록초본", "성적증명서"],
        "body": "경기도 거주 대학생. 소득 7분위 이하, 평점 3.0 이상.",
    },
]


def _key(title: str) -> str:
    return "sample:" + hashlib.sha256(title.encode("utf-8")).hexdigest()[:50]


def clear(db) -> int:
    result = db.execute(
        delete(Scholarship).where(Scholarship.source_platform == SAMPLE_PLATFORM)
    )
    db.commit()
    return result.rowcount or 0


def seed() -> dict:
    init_db()
    db = SessionLocal()
    created = 0
    updated = 0
    try:
        for s in _SAMPLES:
            key = _key(s["title"])
            existing = db.scalar(select(Scholarship).where(Scholarship.content_key == key))
            deadline = s["deadline"]
            if existing is None:
                db.add(
                    Scholarship(
                        content_key=key,
                        title=s["title"],
                        organization=s["organization"],
                        source_type=SourceType.PUBLIC,
                        category=Category.SCHOLARSHIP,
                        source_platform=SAMPLE_PLATFORM,
                        source_url="https://example.com/sample-notice",
                        deadline_at=deadline,
                        eligibility=s["eligibility"],
                        benefit=s["benefit"],
                        required_documents=s["required_documents"],
                        body_text=s["body"],
                        status=PostingStatus.OPEN,
                    )
                )
                created += 1
            else:
                existing.deadline_at = deadline
                existing.eligibility = s["eligibility"]
                existing.benefit = s["benefit"]
                existing.body_text = s["body"]
                existing.status = PostingStatus.OPEN
                updated += 1
        db.commit()
    finally:
        db.close()
    return {"created": created, "updated": updated, "platform": SAMPLE_PLATFORM}


if __name__ == "__main__":
    if "--clear" in sys.argv:
        db = SessionLocal()
        try:
            n = clear(db)
        finally:
            db.close()
        print(json.dumps({"deleted": n}, ensure_ascii=False))
    else:
        print(json.dumps(seed(), ensure_ascii=False, indent=2))
