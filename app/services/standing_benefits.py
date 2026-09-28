"""상시 혜택 카탈로그(한 번 켜면 끝나는 것들).

공고와 다른 종류다. 마감이 없고, 조건을 물어볼 것도 없고(학생이면 대체로
된다), 한 번 신청하면 졸업까지 유지된다. 그래서 위치(지도)에도 대화(챗봇)에도
안 붙고 **체크리스트**가 맞는 형태다.

노력 대비 절감액이 앱 안에서 가장 크지만 아무도 안 한다 — 목록을 몰라서다.

ponytail: 정적 목록이라 테이블을 만들지 않는다. 사용자별 '켰음' 표시만
DB(UserBenefitCheck)에 남긴다. 항목이 수백 개가 되거나 운영자가 화면에서
추가해야 할 때 DB로 승격한다.

**saving_hint_krw 는 연 절감액 추정치다.** 요금제·환급률·학생요금은 수시로
바뀌므로 실제 값과 다를 수 있다. 화면에서 '추정'으로 표시하고, 분기마다
여기 숫자를 손보는 것을 전제로 둔다.
"""
from __future__ import annotations

from app.models.store import SpendCategory


class StandingBenefit(dict):
    """dict 그대로 쓴다. 스키마는 아래 항목들이 곧 문서다."""


#: key 는 사용자 체크 상태의 식별자다. 한 번 정하면 바꾸지 않는다
#: (바꾸면 이미 체크한 사용자의 기록이 끊긴다).
CATALOG: list[dict] = [
    {
        "key": "github-student-pack",
        "title": "GitHub 학생 개발자 팩",
        "category": SpendCategory.STUDY,
        "summary": "JetBrains 전 제품·도메인·클라우드 크레딧이 학생 인증만으로 무료",
        "saving_hint_krw": 300_000,
        "effort_min": 5,
        "credential": "학생 이메일 또는 재학증명",
        "url": "https://education.github.com/pack",
        "search_hint": "GitHub Student Developer Pack",
    },
    {
        "key": "youtube-premium-student",
        "title": "유튜브 프리미엄 학생 요금제",
        "category": SpendCategory.CULTURE,
        "summary": "일반 요금제 대비 매달 절반 수준",
        "saving_hint_krw": 60_000,
        "effort_min": 5,
        "credential": "재학 인증",
        "url": "https://www.youtube.com/premium/student",
        "search_hint": "유튜브 프리미엄 학생 할인",
    },
    {
        "key": "spotify-student",
        "title": "스포티파이 학생 요금제",
        "category": SpendCategory.CULTURE,
        "summary": "학생 인증 시 월 요금 할인",
        "saving_hint_krw": 60_000,
        "effort_min": 5,
        "credential": "재학 인증",
        "url": "https://www.spotify.com/kr-ko/student/",
        "search_hint": "스포티파이 학생 할인",
    },
    {
        "key": "notion-education",
        "title": "노션 교육용 플랜",
        "category": SpendCategory.STUDY,
        "summary": "학교 이메일로 플러스 플랜 무료 전환",
        "saving_hint_krw": 60_000,
        "effort_min": 5,
        "credential": "학교 이메일",
        "url": None,
        "search_hint": "노션 교육용 플랜 학생",
    },
    {
        "key": "figma-education",
        "title": "피그마 교육용 플랜",
        "category": SpendCategory.STUDY,
        "summary": "재학 인증 시 유료 기능 무료",
        "saving_hint_krw": 180_000,
        "effort_min": 10,
        "credential": "재학 인증",
        "url": None,
        "search_hint": "피그마 교육용 학생 인증",
    },
    {
        "key": "ms-office-education",
        "title": "마이크로소프트 오피스 교육용",
        "category": SpendCategory.STUDY,
        "summary": "학교 계정이 있으면 워드·엑셀·파워포인트 무료",
        "saving_hint_krw": 90_000,
        "effort_min": 10,
        "credential": "학교 이메일",
        "url": None,
        "search_hint": "Microsoft 365 Education 학생",
    },
    {
        "key": "k-pass",
        "title": "K-패스 환급",
        "category": SpendCategory.TRANSPORT,
        "summary": "월 15회 이상 대중교통 이용 시 청년 환급률 적용",
        "saving_hint_krw": 240_000,
        "effort_min": 10,
        "credential": None,
        "url": None,
        "search_hint": "K-패스 신청",
    },
    {
        "key": "climate-card",
        "title": "기후동행카드",
        "category": SpendCategory.TRANSPORT,
        "summary": "서울 대중교통 무제한 정액권. 통학이 잦으면 K-패스보다 유리",
        "saving_hint_krw": 120_000,
        "effort_min": 10,
        "credential": None,
        "url": None,
        "search_hint": "기후동행카드 청년",
    },
    {
        "key": "ktx-youth",
        "title": "KTX 청년 할인",
        "category": SpendCategory.TRANSPORT,
        "summary": "만 25세 이하 좌석 할인. 본가 왕복이 잦으면 크다",
        "saving_hint_krw": 80_000,
        "effort_min": 5,
        "credential": "나이 확인",
        "url": None,
        "search_hint": "KTX 청년 할인 힘내라 청춘",
    },
    {
        "key": "mvno-switch",
        "title": "알뜰폰 전환",
        "category": SpendCategory.FIXED,
        "summary": "같은 통신망을 쓰면서 월 요금만 내린다. 번호 그대로 유지",
        "saving_hint_krw": 300_000,
        "effort_min": 30,
        "credential": None,
        "url": None,
        "search_hint": "알뜰폰 요금제 비교",
    },
    {
        "key": "culture-pass",
        "title": "청년 문화예술패스",
        "category": SpendCategory.CULTURE,
        "summary": "공연·전시 관람비 지원. 연 단위로 발급된다",
        "saving_hint_krw": 150_000,
        "effort_min": 15,
        "credential": "나이 확인",
        "url": None,
        "search_hint": "청년 문화예술패스 신청",
    },
    {
        "key": "youth-rent-support",
        "title": "청년 월세 특별지원",
        "category": SpendCategory.FIXED,
        "summary": "자취 중이면 월세 일부를 최대 12개월 지원",
        "saving_hint_krw": 2_400_000,
        "effort_min": 60,
        "credential": "소득·재산 심사",
        "url": None,
        "search_hint": "청년월세 특별지원 신청",
    },
    {
        "key": "student-alliance",
        "title": "학생증 제휴 등록",
        "category": SpendCategory.LIVING,
        "summary": "학교 제휴 매장은 학생증만 보여주면 바로 할인",
        "saving_hint_krw": 50_000,
        "effort_min": 5,
        "credential": "학생증",
        "url": None,
        "search_hint": "우리 학교 제휴 업체",
    },
]

BY_KEY: dict[str, dict] = {item["key"]: item for item in CATALOG}


def total_hint(keys: set[str] | None = None) -> int:
    """미체크 항목의 연 절감액 추정 합계."""
    return sum(
        item["saving_hint_krw"]
        for item in CATALOG
        if keys is None or item["key"] not in keys
    )
