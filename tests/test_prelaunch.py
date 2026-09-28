"""실서비스 공개 전에 보완한 규칙 검증.

여기 있는 규칙은 틀리면 **운영자가 곤란해지는 것**들이다.
  - 동의 없이 가입되면 개인정보 수집 근거가 없다
  - 확인 안 된 주소로 메일이 나가면 남에게 스팸을 보내는 서비스가 된다
  - 수신 거부가 안 먹으면 사용자는 스팸 신고를 누른다
  - 신고를 볼 수 없으면 익명 게시판을 운영할 수 없다
  - 세션이 끝없이 쌓이면 서버가 죽는다
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import (
    UNSUBSCRIBE_PURPOSE,
    VERIFY_PURPOSE,
    read_link_token,
    sign_link_token,
)
from app.models.user import User
from tests.conftest import ADMIN_TOKEN, make_scholarship

EMAIL = "new@khu.ac.kr"
PASSWORD = "new-password-1"
ADMIN = {"X-Admin-Token": ADMIN_TOKEN}


def _signup(client, email=EMAIL, **kw):
    client.cookies.clear()
    body = {"email": email, "password": PASSWORD, "privacy_consent": True, **kw}
    r = client.post("/auth/signup", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _user(db, email=EMAIL) -> User:
    db.expire_all()
    return db.scalar(select(User).where(User.email == email))


# ---------------- 개인정보 동의 ----------------
def test_signup_without_consent_is_rejected(client, db):
    r = client.post("/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 422
    assert _user(db) is None


def test_signup_records_consent_time(client, db):
    _signup(client)
    assert _user(db).privacy_consent_at is not None


# ---------------- 이메일 인증 ----------------
def test_signup_sends_verification_and_link_verifies(client, db, monkeypatch):
    import app.services.mailer as mailer

    urls: list[str] = []
    monkeypatch.setattr(
        mailer, "send_email_verification",
        lambda to, verify_url, ttl_hours: urls.append(verify_url),
    )
    out = _signup(client)
    assert out["email_verified"] is False
    assert len(urls) == 1

    token = urls[0].split("verify_token=")[1]
    client.cookies.clear()  # 메일은 다른 기기에서 열 수 있다
    assert client.post("/auth/email/verify", json={"token": token}).status_code == 204
    assert _user(db).email_verified_at is not None
    # 같은 링크를 다시 눌러도 에러가 아니다
    assert client.post("/auth/email/verify", json={"token": token}).status_code == 204


def test_mail_failure_does_not_block_signup(client, monkeypatch):
    import app.services.mailer as mailer

    def boom(**kw):
        raise OSError("smtp down")

    monkeypatch.setattr(mailer, "send_email_verification", boom)
    _signup(client)


@pytest.mark.parametrize("bad", ["", "garbage", "a.b", "x" * 300])
def test_malformed_token_is_rejected(client, bad):
    assert client.post("/auth/email/verify", json={"token": bad}).status_code == 400


def test_token_purpose_cannot_be_swapped(client, db):
    """수신 거부 링크로 이메일 인증을 통과할 수 있으면 인증이 의미가 없다."""
    _signup(client)
    u = _user(db)
    unsub = sign_link_token(UNSUBSCRIBE_PURPOSE, u.id, u.email)
    assert client.post("/auth/email/verify", json={"token": unsub}).status_code == 400
    assert _user(db).email_verified_at is None


def test_tampered_and_expired_tokens_are_rejected(db, client):
    _signup(client)
    u = _user(db)
    good = sign_link_token(VERIFY_PURPOSE, u.id, u.email, ttl=timedelta(hours=1))
    assert read_link_token(VERIFY_PURPOSE, good) == (u.id, u.email)

    payload, sig = good.split(".")
    assert read_link_token(VERIFY_PURPOSE, f"{payload}x.{sig}") is None
    assert read_link_token(VERIFY_PURPOSE, f"{payload}.{sig[:-2]}AA") is None

    expired = sign_link_token(VERIFY_PURPOSE, u.id, u.email, ttl=timedelta(seconds=-1))
    assert read_link_token(VERIFY_PURPOSE, expired) is None


def test_password_reset_counts_as_verification(client, db):
    from app.core.security import issue_reset_token

    _signup(client)
    raw = issue_reset_token(db, _user(db).id)
    r = client.post(
        "/auth/password/reset", json={"token": raw, "new_password": "brand-new-pass-1"}
    )
    assert r.status_code == 204
    assert _user(db).email_verified_at is not None


# ---------------- 마감 알림 수신 ----------------
def _due_posting(db, now):
    db.add(make_scholarship(content_key="k-due", title="DUE",
                            deadline_at=now + timedelta(days=1, hours=1)))
    db.commit()


def test_reminders_skip_unverified_and_not_opted_in(client, db, monkeypatch):
    import app.services.reminders as reminders

    sent: list[str] = []
    monkeypatch.setattr(
        reminders, "send_deadline_reminder",
        lambda to, items, unsubscribe_url: sent.append(to),
    )
    now = datetime.now(timezone.utc)
    _due_posting(db, now)

    _signup(client, "optin-unverified@khu.ac.kr", reminder_opt_in=True)
    _signup(client, "verified-no-optin@khu.ac.kr")
    _signup(client, "both@khu.ac.kr", reminder_opt_in=True)
    for email in ("verified-no-optin@khu.ac.kr", "both@khu.ac.kr"):
        _user(db, email).email_verified_at = now
    db.commit()

    assert reminders.send_deadline_reminders(db, now) == 1
    assert sent == ["both@khu.ac.kr"]


def test_unsubscribe_link_turns_reminders_off(client, db, monkeypatch):
    import app.services.reminders as reminders

    links: list[str] = []
    monkeypatch.setattr(
        reminders, "send_deadline_reminder",
        lambda to, items, unsubscribe_url: links.append(unsubscribe_url),
    )
    now = datetime.now(timezone.utc)
    _due_posting(db, now)
    _signup(client, reminder_opt_in=True)
    _user(db).email_verified_at = now
    db.commit()
    assert reminders.send_deadline_reminders(db, now) == 1

    token = links[0].split("unsubscribe_token=")[1]
    client.cookies.clear()  # 로그인 없이 동작해야 한다
    r = client.post("/auth/reminders/unsubscribe", json={"token": token})
    assert r.status_code == 204
    assert _user(db).reminder_enabled is False
    assert reminders.send_deadline_reminders(db, now) == 0


def test_reminder_toggle_in_profile(client, db):
    _signup(client)
    r = client.put("/auth/profile", json={"reminder_enabled": True})
    assert r.status_code == 200 and r.json()["reminder_enabled"] is True
    # 다른 필드만 보내면 알림 설정은 그대로다
    r = client.put("/auth/profile", json={"nickname": "닉"})
    assert r.json()["reminder_enabled"] is True


# ---------------- 신고 처리 ----------------
@pytest.fixture()
def reported(client, db):
    """신고 2건이 달린 글 하나와 신고 1건이 달린 댓글 하나."""
    from app.models.community import Board
    from app.scripts.seed_boards import seed_boards

    seed_boards()
    for b in db.scalars(select(Board)).all():
        b.is_active = True
    db.commit()

    _signup(client, "author@khu.ac.kr")
    post = client.post("/community/posts", json={
        "board_slug": "free", "title": "문제 글", "body": "문제 본문"}).json()
    comment = client.post(
        f"/community/posts/{post['id']}/comments", json={"body": "문제 댓글"}
    ).json()

    for email in ("r1@khu.ac.kr", "r2@khu.ac.kr"):
        _signup(client, email)
        r = client.post(f"/community/posts/{post['id']}/report", json={"reason": "허위"})
        assert r.status_code == 204, r.text
    r = client.post(f"/community/comments/{comment['id']}/report", json={"reason": "욕설"})
    assert r.status_code == 204, r.text
    client.cookies.clear()
    return {"post": post["id"], "comment": comment["id"]}


def test_moderation_requires_admin_token(client, reported):
    assert client.get("/admin/moderation/reports").status_code in (401, 403)
    r = client.delete(f"/admin/moderation/posts/{reported['post']}")
    assert r.status_code in (401, 403)


def test_reported_items_are_listed_most_reported_first(client, reported):
    r = client.get("/admin/moderation/reports", headers=ADMIN)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [(x["kind"], x["id"], x["report_count"]) for x in rows] == [
        ("post", reported["post"], 2),
        ("comment", reported["comment"], 1),
    ]
    assert rows[0]["reasons"] == ["허위", "허위"]
    # 신고자·작성자 식별자는 관리자 목록에도 싣지 않는다
    assert "reporter_id" not in str(rows) and "author_id" not in str(rows)


def test_admin_removes_post_and_it_leaves_the_list(client, reported):
    r = client.delete(f"/admin/moderation/posts/{reported['post']}", headers=ADMIN)
    assert r.status_code == 204
    _signup(client, "reader@khu.ac.kr")  # 글 읽기는 로그인이 필요하다
    assert client.get(f"/community/posts/{reported['post']}").status_code == 404
    kinds = [x["kind"] for x in client.get("/admin/moderation/reports", headers=ADMIN).json()]
    assert "post" not in kinds
    # 이미 지운 글을 또 지우면 404
    r = client.delete(f"/admin/moderation/posts/{reported['post']}", headers=ADMIN)
    assert r.status_code == 404


def test_admin_removes_comment(client, db, reported):
    from app.models.community import Comment

    r = client.delete(f"/admin/moderation/comments/{reported['comment']}", headers=ADMIN)
    assert r.status_code == 204
    db.expire_all()
    assert db.get(Comment, reported["comment"]).deleted_at is not None


def test_dismiss_clears_reports_but_keeps_post(client, reported):
    r = client.delete(f"/admin/moderation/posts/{reported['post']}/reports", headers=ADMIN)
    assert r.status_code == 204
    rows = client.get("/admin/moderation/reports", headers=ADMIN).json()
    assert [x["kind"] for x in rows] == ["comment"]
    assert client.delete("/admin/moderation/users/1/reports", headers=ADMIN).status_code == 404


# ---------------- 챗봇 세션 만료 ----------------
def test_chat_sessions_expire_and_are_capped(monkeypatch):
    import app.services.chat as chat

    monkeypatch.setattr(chat, "_SESSIONS", {})
    monkeypatch.setattr(chat, "MAX_SESSIONS", 3)
    clock = [1000.0]
    monkeypatch.setattr(chat.time, "monotonic", lambda: clock[0])

    first = chat.get_or_create_session("s1", None)
    first.history.append(("user", "안녕"))
    clock[0] += 60
    assert chat.get_or_create_session("s1", None) is first   # 살아 있는 세션은 유지

    # 상한: 새 세션이 들어오면 가장 오래 안 쓴 것부터 밀려난다
    for sid in ("s2", "s3", "s4"):
        clock[0] += 1
        chat.get_or_create_session(sid, None)
    assert set(chat._SESSIONS) == {"s2", "s3", "s4"}

    # 만료: 오래 쉰 세션은 같은 ID로 와도 새 대화로 시작한다
    clock[0] += chat.SESSION_IDLE_SEC + 1
    again = chat.get_or_create_session("s2", None)
    assert again.history == []
    assert set(chat._SESSIONS) == {"s2"}


# ---------------- 중단된 크롤 기록 ----------------
def test_stale_running_crawl_is_closed_on_next_run(db, monkeypatch):
    import app.crawlers.registry as registry
    from app.models.crawl_run import CrawlRun, CrawlRunStatus

    monkeypatch.setattr(registry, "REGISTRY", [])
    now = datetime.now(timezone.utc)
    dead = CrawlRun(trigger="scheduled", status=CrawlRunStatus.RUNNING,
                    started_at=now - timedelta(hours=3))
    fresh = CrawlRun(trigger="manual", status=CrawlRunStatus.RUNNING,
                     started_at=now - timedelta(minutes=5))
    db.add_all([dead, fresh])
    db.commit()

    run = registry.run_daily_update(db, trigger="manual")
    db.expire_all()
    assert run.status == CrawlRunStatus.SUCCESS
    assert db.get(CrawlRun, dead.id).status == CrawlRunStatus.FAILED
    assert db.get(CrawlRun, dead.id).finished_at is not None
    # 방금 시작한 다른 실행은 건드리지 않는다
    assert db.get(CrawlRun, fresh.id).status == CrawlRunStatus.RUNNING


# ---------------- 거절한 업로드 파일 ----------------
def test_rejected_upload_leaves_no_file(auth_client):
    import os

    from app.core.config import settings

    before = set(os.listdir(settings.upload_dir)) if os.path.isdir(settings.upload_dir) else set()
    r = auth_client.post(
        "/chat/upload", files={"file": ("virus.exe", b"MZ\x90\x00", "application/octet-stream")}
    )
    assert r.status_code == 415
    after = set(os.listdir(settings.upload_dir))
    assert after - before == set()
