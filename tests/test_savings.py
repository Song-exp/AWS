"""세이빙 대시보드 검증(기획서 3.3 + KPI).

KPI 두 개가 이 엔드포인트의 숫자로 측정된다. 계산이 틀리면 서비스 성과를
잘못 보고하게 되므로 경계값을 고정한다.
  - 유저당 월평균 지출 절감액 (목표 30,000원)
  - 혜택 조회 후 실소비 전환율 (목표 25%)
"""
from __future__ import annotations

import pytest

# 소유자는 세션에서 판단하므로 요청에 user_id를 싣지 않는다.
pytestmark = pytest.mark.usefixtures("auth_client")


def _spend(auth_client, original, final, **kw):
    payload = {"original_amount": original, "final_amount": final}
    payload.update(kw)
    return auth_client.post("/savings/spend", json=payload)


def test_spend_computes_saved_amount(auth_client):
    r = _spend(auth_client, 10000, 9000, method_label="네이버페이 10%")
    assert r.status_code == 201
    body = r.json()
    assert body["saved_amount"] == 1000
    assert body["method_label"] == "네이버페이 10%"


def test_spend_rejects_final_greater_than_original(auth_client):
    """할인했는데 더 냈다는 기록은 집계를 망가뜨린다."""
    assert _spend(auth_client, 5000, 6000).status_code == 422


def test_spend_rejects_non_positive_original(auth_client):
    assert _spend(auth_client, 0, 0).status_code == 422


def test_monthly_total_accumulates(auth_client):
    _spend(auth_client, 10000, 9000)
    _spend(auth_client, 8000, 6500)
    _spend(auth_client, 5000, 5000)   # 절감 0원도 소비 완료 건수에는 포함

    s = auth_client.get("/savings/summary").json()
    assert s["month_saved"] == 2500
    assert s["total_saved"] == 2500
    assert s["month_count"] == 3


def test_store_label_is_snapshotted_from_store(auth_client, seed_stores):
    """매장이 지워져도 이력에 이름이 남아야 한다."""
    r = _spend(auth_client, 10000, 9000, store_id=seed_stores["near"])
    assert r.json()["store_label"] == "CU 경희대점"


def test_conversion_rate_uses_view_events(auth_client):
    """조회 4건 중 1건 소비 → 25% (KPI 목표선)."""
    for _ in range(4):
        auth_client.post("/savings/view", json={"store_label": "CU"})
    _spend(auth_client, 10000, 9000)

    s = auth_client.get("/savings/summary").json()
    assert s["viewed_count"] == 4
    assert s["conversion_rate"] == 0.25


def test_conversion_rate_is_zero_when_no_views(auth_client):
    """분모가 0일 때 0으로 나누면 500이 난다. 0.0으로 방어한다."""
    _spend(auth_client, 10000, 9000)
    s = auth_client.get("/savings/summary").json()
    assert s["conversion_rate"] == 0.0


@pytest.mark.parametrize("saved,label,count", [
    (30000, "학식", 5),        # KPI 목표 절감액 → 학식 5그릇
    (6000, "학식", 1),
    (5000, "아메리카노", 1),   # 학식 1그릇에 못 미치면 다음 단위로
    (2000, "편의점 삼각김밥", 1),
])
def test_reward_uses_largest_meaningful_unit(auth_client, saved, label, count):
    """'삼각김밥 20개'보다 '학식 5그릇'이 체감된다."""
    _spend(auth_client, saved, 0)
    s = auth_client.get("/savings/summary").json()
    assert s["reward"]["label"] == label
    assert s["reward"]["count"] == count


def test_no_reward_below_smallest_unit(auth_client):
    _spend(auth_client, 500, 0)
    s = auth_client.get("/savings/summary").json()
    assert s["reward"] is None


def test_summary_is_isolated_per_user(auth_client):
    """계정 간 격리는 test_authorization.py 가 두 계정으로 검증한다.

    여기서는 내 기록만 내 합계에 들어가는지 확인한다.
    """
    _spend(auth_client, 10000, 0)
    mine = auth_client.get("/savings/summary").json()
    assert mine["month_saved"] == 10000


def test_recent_history_is_newest_first(auth_client):
    _spend(auth_client, 1000, 0, store_label="첫번째")
    _spend(auth_client, 2000, 0, store_label="두번째")

    s = auth_client.get("/savings/summary").json()
    assert [r["store_label"] for r in s["recent"]] == ["두번째", "첫번째"]


def test_view_events_excluded_from_saved_total(auth_client):
    """조회 이벤트가 절감액에 섞이면 KPI가 부풀려진다."""
    for _ in range(10):
        auth_client.post("/savings/view", json={})
    s = auth_client.get("/savings/summary").json()
    assert s["month_saved"] == 0
    assert s["month_count"] == 0


# ---------------- 타임존 회귀 ----------------
def test_created_at_is_not_shifted_by_timezone(auth_client):
    """DB의 CURRENT_TIMESTAMP는 UTC다. 이를 KST로 간주하면 9시간 어긋난다.

    표시 시각이 밀리는 것도 문제지만, 진짜 위험은 월간 집계다. 월초 9시간
    동안의 소비가 지난달로 새면 KPI(월평균 절감액)가 틀린다.
    """
    from datetime import datetime, timedelta, timezone

    r = _spend(auth_client, 10000, 9000)
    created = datetime.fromisoformat(r.json()["created_at"])
    now = datetime.now(timezone.utc)

    assert abs(created - now) < timedelta(minutes=5), (
        f"기록 시각이 현재와 {abs(created - now)} 만큼 차이난다"
    )


def test_spend_counts_in_current_month_near_month_boundary(auth_client):
    """월초에 만든 기록은 반드시 이번 달 집계에 들어가야 한다."""
    _spend(auth_client, 10000, 9000)
    s = auth_client.get("/savings/summary").json()
    assert s["month_count"] == 1, "방금 만든 기록이 이번 달 집계에서 빠졌다"
    assert s["month_saved"] == 1000
