"""매칭 엔진 검증.

하드필터가 뚫리면 자격 없는 공고를 추천하게 된다 — 이 서비스의 신뢰가
걸린 지점이라 경계값을 명시적으로 고정한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.schemas.schemas import UserProfile
from app.services.matching import match_scholarships
from tests.conftest import make_scholarship

KST = timezone(timedelta(hours=9))


def test_income_bracket_excludes_ineligible(db):
    db.add(make_scholarship(content_key="k1", title="저소득",
                            eligibility={"income_bracket": [0, 1, 2]}))
    db.commit()

    assert match_scholarships(db, UserProfile(income_bracket=1)) != []
    assert match_scholarships(db, UserProfile(income_bracket=5)) == []


def test_gpa_boundary_is_inclusive(db):
    """기준 학점과 '같으면' 통과여야 한다(>= 기준)."""
    db.add(make_scholarship(content_key="k2", title="성적",
                            eligibility={"gpa_min": 3.5}))
    db.commit()

    assert match_scholarships(db, UserProfile(gpa=3.5)) != []   # 경계값 포함
    assert match_scholarships(db, UserProfile(gpa=3.49)) == []


def test_region_nationwide_passes_any_region(db):
    db.add(make_scholarship(content_key="k3", title="전국",
                            eligibility={"region": ["전국"]}))
    db.add(make_scholarship(content_key="k4", title="서울만",
                            eligibility={"region": ["서울"]}))
    db.commit()

    titles = {r.scholarship.title for r in match_scholarships(db, UserProfile(region="부산"))}
    assert titles == {"전국"}


def test_missing_profile_field_does_not_exclude(db):
    """사용자가 아직 말하지 않은 조건으로 공고를 걸러내면 안 된다.

    대화 초반에는 프로필이 비어 있다. 여기서 전부 탈락시키면 챗봇이
    '조건에 맞는 공고가 없다'고 잘못 답하게 된다.
    """
    db.add(make_scholarship(content_key="k5", title="소득제한",
                            eligibility={"income_bracket": [0, 1]}))
    db.commit()

    assert match_scholarships(db, UserProfile()) != []


def test_closed_postings_are_never_returned(db):
    from app.models.scholarship import PostingStatus

    db.add(make_scholarship(content_key="k6", title="마감", status=PostingStatus.CLOSED))
    db.add(make_scholarship(content_key="k7", title="검토필요",
                            status=PostingStatus.NEEDS_REVIEW))
    db.commit()

    assert match_scholarships(db, UserProfile()) == []


def test_imminent_deadline_ranks_higher(db):
    now = datetime.now(KST)
    db.add(make_scholarship(content_key="k8", title="임박",
                            deadline_at=now + timedelta(days=2)))
    db.add(make_scholarship(content_key="k9", title="여유",
                            deadline_at=now + timedelta(days=25)))
    db.commit()

    results = match_scholarships(db, UserProfile())
    assert results[0].scholarship.title == "임박"


def test_naive_deadline_does_not_crash(db):
    """SQLite는 tz를 저장하지 않아 naive datetime을 돌려준다.

    aware/naive를 섞어 빼면 TypeError가 난다. _as_aware 보정이 살아있는지 고정.
    """
    db.add(make_scholarship(content_key="k10", title="naive",
                            deadline_at=datetime.now() + timedelta(days=5)))
    db.commit()

    results = match_scholarships(db, UserProfile())  # 예외 없이 돌아야 한다
    assert len(results) == 1


def test_reasons_explain_why_it_matched(db):
    """추천 근거가 비어 있으면 사용자가 결과를 신뢰할 수 없다."""
    db.add(make_scholarship(content_key="k11", title="근거",
                            eligibility={"income_bracket": [3], "gpa_min": 3.0}))
    db.commit()

    r = match_scholarships(db, UserProfile(income_bracket=3, gpa=4.0))[0]
    assert any("소득" in x for x in r.reasons)
    assert any("학점" in x for x in r.reasons)


def test_limit_is_respected(db):
    for i in range(30):
        db.add(make_scholarship(content_key=f"lim{i}", title=f"공고{i}"))
    db.commit()

    assert len(match_scholarships(db, UserProfile(), limit=5)) == 5
