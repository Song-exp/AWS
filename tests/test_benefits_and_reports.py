"""혜택 탭(공고 목록·상시 혜택)과 끝난 혜택 제보 검증.

이번 개편에서 새로 생긴 규칙 중 **틀리면 사용자가 손해를 보는 것**만 고른다.
  - 끝난 혜택이 추천 1순위로 밀리면 헛걸음한다
  - 제보가 여러 번 세지면 임계가 무의미해진다
  - 매장 결제에 분야가 안 붙으면 대시보드가 빈다
  - 마감 알림이 매일 오면 사용자가 알림을 끈다
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone

from app.models.scholarship import Scholarship
from tests.conftest import ADMIN_TOKEN, make_scholarship


def _login(client, email="user@khu.ac.kr", password="user-password-1"):
    client.cookies.clear()
    r = client.post("/auth/signup", json={"privacy_consent": True, "email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------- 상시 혜택 ----------------
def test_standing_benefits_are_listed_without_login(client):
    """뭘 받을 수 있는지 보려고 가입부터 하라고 하면 아무도 안 본다."""
    r = client.get("/benefits/items")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["items"]) > 0
    assert data["remaining_count"] == len(data["items"])   # 비로그인은 전부 미체크
    assert data["remaining_hint_krw"] > 0


def test_check_toggles_and_moves_to_the_end(client):
    _login(client)
    key = client.get("/benefits/items").json()["items"][0]["key"]

    r = client.post(f"/benefits/items/{key}/check")
    assert r.json() == {"active": True, "count": 1}

    after = client.get("/benefits/items").json()
    done = [i for i in after["items"] if i["key"] == key][0]
    assert done["done"] is True
    assert after["items"][-1]["done"] is True     # 켠 항목은 뒤로 밀린다
    assert after["remaining_count"] == len(after["items"]) - 1

    # 오탭 복구
    assert client.post(f"/benefits/items/{key}/check").json()["active"] is False


def test_unknown_benefit_key_is_404(client):
    _login(client)
    assert client.post("/benefits/items/nope/check").status_code == 404


# ---------------- 공고 목록 ----------------
def test_postings_are_listed_deadline_first(client, db):
    """이 목록이 시간축을 대신한다. 급한 게 위로 와야 한다."""
    now = datetime.now(timezone.utc)
    db.add_all([
        make_scholarship(content_key="k-late", title="여유",
                         deadline_at=now + timedelta(days=30)),
        make_scholarship(content_key="k-soon", title="임박",
                         deadline_at=now + timedelta(days=2)),
        make_scholarship(content_key="k-none", title="마감없음", deadline_at=None),
    ])
    db.commit()

    items = client.get("/scholarships").json()["items"]
    assert [i["title"] for i in items] == ["임박", "여유", "마감없음"]
    assert items[0]["days_left"] <= 2


def test_closed_postings_are_hidden_by_default(client, db):
    from app.models.scholarship import PostingStatus

    db.add(make_scholarship(content_key="k-closed", title="끝남",
                            status=PostingStatus.CLOSED))
    db.commit()
    assert client.get("/scholarships").json()["total"] == 0
    assert client.get(
        "/scholarships", params={"include_closed": True}
    ).json()["total"] == 1


def test_posting_detail_carries_apply_url(client, db):
    row = make_scholarship(content_key="k-detail", title="상세")
    db.add(row)
    db.commit()
    got = client.get(f"/scholarships/{row.id}").json()
    assert got["source_url"].startswith("http")   # 신청은 외부 링크로 나간다
    assert "eligibility" in got


# ---------------- 끝난 혜택 제보 ----------------
def test_report_toggles_and_counts_once_per_user(client, db, seed_stores):
    offer_id = client.get(f"/stores/{seed_stores['near']}").json()["offers"][0]["id"]

    _login(client, "a@khu.ac.kr", "a-password-1")
    assert client.post(f"/stores/offers/{offer_id}/report").json()["count"] == 1
    # 같은 사람이 또 눌러도 2가 되지 않는다 — 취소다
    assert client.post(f"/stores/offers/{offer_id}/report").json() == {
        "active": False, "count": 0, "flagged": False
    }

    _login(client, "b@khu.ac.kr", "b-password-1")
    assert client.post(f"/stores/offers/{offer_id}/report").json()["count"] == 1


def test_reported_offer_drops_out_of_best_deal(client, seed_stores, monkeypatch):
    """끝난 혜택을 1순위로 밀어주는 것만은 막는다."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "store_offer_report_threshold", 1)

    store_id = seed_stores["near"]
    before = client.get(f"/stores/{store_id}").json()
    assert before["best_deal"]["kind"] == "simple_pay"
    offer_id = before["offers"][0]["id"]

    _login(client, "c@khu.ac.kr", "c-password-1")
    assert client.post(f"/stores/offers/{offer_id}/report").json()["flagged"] is True

    after = client.get(f"/stores/{store_id}").json()
    assert after["best_deal"] is None          # 추천에서 빠지고
    assert len(after["offers"]) == 1           # 목록에는 남는다
    assert after["offers"][0]["reported"] is True
    assert after["offers"][0]["report_count"] == 1


def test_report_requires_login(client, seed_stores):
    offer_id = client.get(f"/stores/{seed_stores['near']}").json()["offers"][0]["id"]
    assert client.post(f"/stores/offers/{offer_id}/report").status_code == 401


def test_admin_can_see_reported_offers(client, seed_stores):
    offer_id = client.get(f"/stores/{seed_stores['near']}").json()["offers"][0]["id"]
    _login(client, "d@khu.ac.kr", "d-password-1")
    client.post(f"/stores/offers/{offer_id}/report")

    r = client.get("/admin/offer-reports", headers={"X-Admin-Token": ADMIN_TOKEN})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows[0]["offer_id"] == offer_id
    assert rows[0]["report_count"] == 1
    assert rows[0]["is_active"] is True        # 자동 비활성은 하지 않는다


# ---------------- 절감 분야 ----------------
def test_store_spend_gets_category_from_store_type(client, seed_stores):
    """지도에서 온 기록은 클라이언트가 분야를 안 보내도 서버가 채운다."""
    _login(client, "e@khu.ac.kr", "e-password-1")
    r = client.post("/savings/spend", json={
        "store_id": seed_stores["near"],
        "original_amount": 5000, "final_amount": 4500,
    })
    assert r.status_code == 201, r.text
    assert r.json()["category"] == "food"      # 편의점 -> 식비


def test_non_store_spend_keeps_its_own_category(client):
    """이 컬럼이 없으면 교통·구독 절감을 기록할 방법이 아예 없다."""
    _login(client, "f@khu.ac.kr", "f-password-1")
    r = client.post("/savings/spend", json={
        "store_label": "K-패스 환급", "category": "transport",
        "original_amount": 60000, "final_amount": 42000,
    })
    assert r.status_code == 201, r.text

    summary = client.get("/savings/summary").json()
    by_cat = {c["category"]: c for c in summary["by_category"]}
    assert by_cat["transport"]["saved"] == 18000
    assert by_cat["transport"]["label"] == "교통"


# ---------------- 등급 ----------------
def test_tier_rises_with_savings(client):
    _login(client, "g@khu.ac.kr", "g-password-1")
    assert client.get("/savings/summary").json()["tier"]["label"] == "씨앗"

    client.post("/savings/spend", json={
        "store_label": "알뜰폰 전환", "category": "fixed",
        "original_amount": 60000, "final_amount": 0,
    })
    tier = client.get("/savings/summary").json()["tier"]
    assert tier["label"] == "알뜰"
    assert tier["next_label"] == "절약러"


def test_tier_is_demoted_by_reports(client, db, monkeypatch):
    """등급이 '많이 아꼈다'만 뜻하면 자랑 뱃지다. 틀린 정보로 깎여야 신뢰가 된다."""
    from app.core.config import settings
    from app.models.community import Report
    from app.scripts.seed_boards import seed_boards
    from app.services.tier import compute_tier

    monkeypatch.setattr(settings, "community_report_demote_threshold", 2)
    seed_boards()

    me = _login(client, "h@khu.ac.kr", "h-password-1")
    client.post("/savings/spend", json={
        "store_label": "x", "category": "food",
        "original_amount": 60000, "final_amount": 0,
    })
    user_id = _uuid.UUID(me["id"])
    assert compute_tier(db, user_id).label == "알뜰"

    post = client.post("/community/posts", json={
        "board_slug": "saving-tips", "title": "틀린 정보", "body": "본문",
    }).json()
    for _ in range(2):
        db.add(Report(post_id=post["id"], reporter_id=_uuid.uuid4(), reason="fake"))
    db.commit()

    demoted = compute_tier(db, user_id)
    assert demoted.label == "새싹"
    assert demoted.demoted is True


# ---------------- 마감 리마인더 ----------------
def test_reminder_fires_only_on_exact_days(client, db):
    """'7일 이하 전부'로 하면 같은 공고가 이레 내내 온다."""
    from app.services.reminders import due_postings

    now = datetime.now(timezone.utc)
    for key, days in (("d7", 7), ("d5", 5), ("d1", 1)):
        db.add(make_scholarship(
            content_key=f"k-{key}", title=key,
            deadline_at=now + timedelta(days=days, hours=1),
        ))
    db.commit()

    due = due_postings(db, now)
    titles = {db.get(Scholarship, sid).title for sid in due}
    assert titles == {"d7", "d1"}     # D-5 는 설정(7,3,1)에 없다


def test_reminder_mail_is_one_message_per_user(client, db, monkeypatch):
    import app.services.reminders as reminders

    sent: list[tuple] = []
    monkeypatch.setattr(
        reminders, "send_deadline_reminder",
        lambda to, items, unsubscribe_url: sent.append((to, items)),
    )

    now = datetime.now(timezone.utc)
    db.add_all([
        make_scholarship(content_key="k-a", title="A",
                         deadline_at=now + timedelta(days=1, hours=1)),
        make_scholarship(content_key="k-b", title="B",
                         deadline_at=now + timedelta(days=3, hours=1)),
    ])
    db.commit()
    _login(client, "i@khu.ac.kr", "i-password-1")
    # 알림은 수신에 동의하고 주소가 확인된 사용자에게만 간다
    from app.models.user import User

    me = db.query(User).one()
    me.reminder_enabled, me.email_verified_at = True, now
    db.commit()

    assert reminders.send_deadline_reminders(db, now) == 1
    to, items = sent[0]
    assert to == "i@khu.ac.kr"
    assert len(items) == 2                       # 공고마다 따로 보내지 않는다
    assert items[0]["days_left"] <= items[1]["days_left"]
