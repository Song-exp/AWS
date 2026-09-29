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


# ---------------- 남용 방지 (보안 검토 대응) ----------------
def test_forged_forwarded_for_cannot_reset_the_counter(client, db, monkeypatch):
    """X-Forwarded-For 앞쪽은 클라이언트가 써넣을 수 있다.

    그 값을 믿으면 헤더 한 줄로 로그인 상한이 사라져 비밀번호를 무한히
    시도할 수 있다.
    """
    from app.core.config import settings
    from app.core.security import _reset_rate_limit

    _signup(client)
    _reset_rate_limit()
    monkeypatch.setattr(settings, "auth_rate_limit_per_min", 3)
    client.cookies.clear()

    codes = [
        client.post(
            "/auth/login",
            json={"email": EMAIL, "password": f"wrong-{i}"},
            headers={"X-Forwarded-For": f"10.0.0.{i}"},  # 매번 다른 위조 IP
        ).status_code
        for i in range(6)
    ]
    assert 429 in codes, codes


def test_login_limit_is_per_account_too(client, monkeypatch):
    """IP를 바꿔가며 한 계정만 두드리는 경우도 막아야 한다."""
    from app.core.config import settings
    from app.core.security import _reset_rate_limit

    _signup(client)
    _reset_rate_limit()
    monkeypatch.setattr(settings, "auth_rate_limit_per_min", 3)
    client.cookies.clear()

    # 상한을 넘긴 뒤 다른 계정으로는 여전히 시도할 수 있어야 한다.
    for i in range(5):
        client.post("/auth/login", json={"email": EMAIL, "password": f"w-{i}"})
    blocked = client.post("/auth/login", json={"email": EMAIL, "password": "w"})
    assert blocked.status_code == 429
    _reset_rate_limit()
    other = client.post(
        "/auth/login", json={"email": "someone-else@khu.ac.kr", "password": "w"}
    )
    assert other.status_code == 401


def test_ai_endpoints_require_login(client):
    """두 엔드포인트 모두 유료 LLM을 호출한다. 계정 없이 열려 있으면 비용이 샌다."""
    for path, body in (
        ("/ai/qa", {"question": "장학금 알려줘"}),
        ("/ai/draft", {"scholarship_id": 1, "questions": ["q"]}),
    ):
        assert client.post(path, json=body).status_code == 401, path


def test_non_ascii_token_returns_400_not_500(client):
    """잘못된 토큰은 400이어야 한다. 여기서 예외가 새면 500이 난다."""
    for path in ("/auth/email/verify", "/auth/reminders/unsubscribe"):
        r = client.post(path, json={"token": "abc.아"})
        assert r.status_code == 400, (path, r.status_code)


def test_non_ascii_admin_token_returns_401_not_500():
    """FastAPI 는 헤더를 latin-1 로 디코딩한다. 그 문자열을 그대로 비교하면
    TypeError 가 나서 500이 된다. 여기서는 401이어야 한다.

    테스트 클라이언트가 비ASCII 헤더를 실어 보내지 못하므로 함수를 직접 부른다.
    """
    from fastapi import HTTPException

    from app.core.security import require_admin

    with pytest.raises(HTTPException) as e:
        require_admin(x_admin_token="토큰".encode().decode("latin-1"))
    assert e.value.status_code == 401


def test_oversized_upload_is_cut_off(auth_client, monkeypatch):
    """상한을 넘는 본문은 전부 읽지 않고 끊어야 한다. 읽으면 메모리가 터진다."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_upload_mb", 1)
    big = b"x" * (2 * 1024 * 1024)
    r = auth_client.post("/chat/upload", files={"file": ("big.txt", big, "text/plain")})
    assert r.status_code == 413, r.status_code


def test_zip_bomb_is_rejected(tmp_path, monkeypatch):
    """10MB 파일이 수 GB로 부푸는 압축 폭탄을 파싱하면 워커가 죽는다."""
    import zipfile

    import app.utils.file_parser as fp

    monkeypatch.setattr(fp, "MAX_UNCOMPRESSED_BYTES", 1024 * 1024)
    bomb = tmp_path / "bomb.hwpx"
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Contents/section0.xml", b"\0" * (4 * 1024 * 1024))
    assert bomb.stat().st_size < 1024 * 1024  # 압축 상태로는 작다

    with pytest.raises(fp.UnsupportedFileType):
        fp.extract_text(str(bomb))


def test_real_user_data_in_data_dir_is_gitignored():
    """DB 백업과 업로드 백업이 git add 한 번에 공개되면 안 된다."""
    import subprocess

    for path in (
        "data/app.db",
        "data/app.db.pre-crawl-20260928",
        "data/backup-before-account-wipe-20260922/app.db",
        "data/uploads/x.pdf",
    ):
        r = subprocess.run(["git", "check-ignore", path], capture_output=True)
        assert r.returncode == 0, f"{path} 가 .gitignore 에 걸리지 않는다"


# ---------------- 개인정보가 외부 LLM으로 새지 않는지 ----------------
def test_past_answers_are_masked_before_leaving_for_the_llm(auth_client, db, monkeypatch):
    """과거 신청서 본문은 외부 LLM으로 그대로 나간다.

    신청서에는 주민번호·연락처가 섞여 있다. 임베딩 전에는 마스킹하고 있었는데
    초안 생성 프롬프트에는 원문이 실려 나갔다.
    """
    import app.services.llm as llm

    created = auth_client.post(
        "/applications",
        json={
            "scholarship_name": "과거 신청서",
            "documents": [{
                "doc_type": "self_intro",
                "content_text": "주민번호 990101-1234567, 연락처 010-1234-5678 입니다.",
            }],
        },
    )
    assert created.status_code == 200, created.text

    prompts: list[str] = []
    monkeypatch.setattr(llm, "has_llm", lambda: True)
    monkeypatch.setattr(
        llm, "chat_complete",
        lambda system, user, **kw: prompts.append(user) or "초안",
    )

    sch = make_scholarship(content_key="k-draft", title="대상 장학금")
    db.add(sch)
    db.commit()
    r = auth_client.post(
        "/ai/draft", json={"scholarship_id": sch.id, "questions": ["지원 동기"]}
    )
    assert r.status_code == 200, r.text

    assert prompts, "LLM 호출이 없었다"
    sent = "\n".join(prompts)
    assert "990101-1234567" not in sent
    assert "010-1234-5678" not in sent
    # 마스킹만 하고 답변 자체는 근거로 남아야 한다
    assert "입니다" in sent


def test_crawler_attachment_zip_bomb_is_rejected(monkeypatch):
    """크롤러가 받는 첨부도 사용자 업로드와 같은 검사를 지나야 한다."""
    import io
    import zipfile

    import app.utils.file_parser as fp

    monkeypatch.setattr(fp, "MAX_UNCOMPRESSED_BYTES", 1024 * 1024)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", b"\0" * (4 * 1024 * 1024))

    with pytest.raises(fp.UnsupportedFileType):
        fp.extract_text_from_bytes(buf.getvalue(), "attach.docx")


# ---------------- 주민등록번호 비보관 ----------------
def test_resident_number_is_not_stored(auth_client, db):
    """주민등록번호는 법령 근거 없이 보관할 수 없다. 물어보지 않지만 올린
    신청서 안에 들어 있을 수 있어 저장 전에 지운다."""
    from app.models.application import ApplicationDocument

    body = "저는 990101-1234567 입니다. 학번 2020123456, 계좌 1002-345-678901."
    r = auth_client.post(
        "/applications/upload",
        data={"scholarship_name": "테스트 장학금"},
        files={"file": ("intro.txt", body.encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 200, r.text

    text = "\n".join(db.scalars(select(ApplicationDocument.content_text)).all())
    assert text, "문서가 저장되지 않았다"
    assert "990101-1234567" not in text
    # 학번·계좌처럼 초안의 근거가 되는 숫자는 남아야 한다
    assert "2020123456" in text and "1002-345-678901" in text


def test_uploaded_original_file_is_not_kept(auth_client, db):
    """원본 파일에는 지운 번호가 그대로 남아 있다. 다시 읽는 곳도 없다."""
    import os

    from app.core.config import settings
    from app.models.application import UserApplication

    before = set(os.listdir(settings.upload_dir)) if os.path.isdir(settings.upload_dir) else set()
    r = auth_client.post(
        "/applications/upload",
        data={"scholarship_name": "테스트 장학금"},
        files={"file": ("intro.txt", "본문 990101-1234567".encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 200, r.text

    assert set(os.listdir(settings.upload_dir)) - before == set()
    row = db.scalars(select(UserApplication)).first()
    assert row.source_file_path is None


def test_typed_and_edited_text_is_stripped_too(auth_client):
    """업로드뿐 아니라 직접 작성·수정 경로도 같은 규칙을 지나야 한다."""
    created = auth_client.post(
        "/applications",
        json={
            "scholarship_name": "직접 작성",
            "documents": [{"doc_type": "self_intro", "content_text": "제 번호 0012313456789"}],
        },
    )
    assert created.status_code == 200, created.text
    assert "0012313456789" not in str(created.json())

    doc_id = created.json()["documents"][0]["id"]
    edited = auth_client.put(
        f"/me/applications/{created.json()['id']}/documents",
        json={"documents": [{"id": doc_id, "content_text": "다시 011231-4567890 씁니다"}]},
    )
    assert edited.status_code == 200, edited.text
    assert "011231-4567890" not in str(edited.json())


@pytest.mark.parametrize(
    "text",
    [
        "991301-1234567",   # 13월
        "990132-1234567",   # 32일
        "990101-9234567",   # 성별코드 9
        "1234567890123",    # 날짜 형식이 아닌 13자리
        "1002-345-678901",  # 계좌번호
    ],
)
def test_stripping_does_not_eat_other_numbers(text):
    """계좌·학번이 같이 지워지면 초안의 근거가 망가진다."""
    from app.utils.pii import strip_rrn

    assert strip_rrn(text) == text


# ---------------- NUL 바이트 ----------------
def test_nul_bytes_are_stripped_before_saving_postings(db):
    """PostgreSQL 은 text·jsonb 에 NUL 을 담지 못한다. 넣으려 하면 트랜잭션이
    통째로 실패한다. SQLite 는 받아주므로 로컬에서는 드러나지 않는다."""
    from app.crawlers.base import RawPosting
    from app.crawlers.registry import upsert_posting
    from app.models.scholarship import Category, Scholarship, SourceType

    raw = RawPosting(
        source_platform="test",
        source_url="https://example.test/nul\x00",
        title="제목\x00에 섞임",
        organization="기관\x00",
        source_type=SourceType.PRIVATE,
        category=Category.SCHOLARSHIP,
        body_text="본문\x00에도 섞임",
        eligibility={"scope": "재학생\x00", "tags": ["가\x00나"]},
        benefit={"amount_desc": "100만원\x00"},
        required_documents=["서류\x00"],
    )
    assert upsert_posting(db, raw) is True
    db.commit()

    row = db.scalars(select(Scholarship)).one()
    blob = f"{row.title}{row.organization}{row.body_text}{row.source_url}"
    blob += f"{row.eligibility}{row.benefit}{row.required_documents}"
    assert "\x00" not in blob
    assert row.title == "제목에 섞임"
    assert row.eligibility["tags"] == ["가나"]


def test_nul_bytes_are_stripped_from_uploaded_documents(auth_client, db):
    """업로드 문서는 크롤 첨부와 같은 파서를 쓴다. 같은 문제를 받는다."""
    from app.models.application import ApplicationDocument

    r = auth_client.post(
        "/applications/upload",
        data={"scholarship_name": "테스트"},
        files={"file": ("a.txt", "본문\x00입니다".encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 200, r.text
    text = db.scalars(select(ApplicationDocument.content_text)).one()
    assert "\x00" not in text and text == "본문입니다"


def test_strip_nul_leaves_other_text_alone():
    from app.utils.text import strip_nul

    assert strip_nul("정상 텍스트") == "정상 텍스트"
    assert strip_nul({"a": ["x"], "n": 3, "b": None}) == {"a": ["x"], "n": 3, "b": None}
