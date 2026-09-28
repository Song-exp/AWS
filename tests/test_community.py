"""커뮤니티 검증.

이 도메인에서 가장 위험한 버그는 '익명이 아닌 것'이다. 사람들은 익명을
믿고 글을 쓰는데, 응답 어딘가에 작성자 식별자가 실리면 그 신뢰가 한 번에
깨진다. 그래서 익명 누출을 가장 먼저, 가장 촘촘히 검사한다.
"""
from __future__ import annotations

import pytest

A = ("alice@khu.ac.kr", "alice-password-1")
B = ("bob@khu.ac.kr", "bob-password-1")


@pytest.fixture()
def boards(db):
    """시드 후 전 게시판을 켠다.

    운영 기본값은 활성 2개(절약 꿀팁·공동구매)지만, 익명 정책 분기와
    익명 번호 로직은 코드에 그대로 남아 있다(비활성 게시판을 되살릴 여지).
    남아 있는 로직은 계속 검증해야 하므로 이 파일은 전 게시판을 켜고 돈다.
    시드 기본값 자체는 test_seed_* 가 따로 지킨다.
    """
    from sqlalchemy import select

    from app.models.community import Board
    from app.scripts.seed_boards import seed_boards

    seed_boards()
    for b in db.scalars(select(Board)).all():
        b.is_active = True
    db.commit()
    return db


def _login_as(client, creds):
    client.cookies.clear()
    r = client.post("/auth/signup", json={"email": creds[0], "password": creds[1]})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": creds[0], "password": creds[1]})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _write(client, slug="free", title="제목", body="본문", **kw):
    payload = {"board_slug": slug, "title": title, "body": body}
    payload.update(kw)
    r = client.post("/community/posts", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------- 익명 ----------------
def test_anonymous_post_never_exposes_author(client, boards):
    """응답 어디에도 작성자 식별자가 없어야 한다."""
    _login_as(client, A)
    post = _write(client, is_anonymous=True)

    assert post["author_label"] == "익명"
    body = str(post)
    assert "alice" not in body
    assert "author_id" not in post


def test_anonymous_post_hides_author_from_others(client, boards):
    alice = _login_as(client, A)
    post = _write(client, is_anonymous=True)

    _login_as(client, B)
    seen = client.get(f"/community/posts/{post['id']}").json()
    assert seen["author_label"] == "익명"
    assert seen["is_mine"] is False
    assert alice["id"] not in str(seen)


def test_named_post_shows_nickname(client, boards):
    _login_as(client, A)
    client.put("/auth/profile", json={"nickname": "앨리스"})
    post = _write(client, is_anonymous=False)
    assert post["author_label"] == "앨리스"


def test_same_commenter_keeps_one_number_within_a_post(client, boards):
    """같은 사람이 댓글마다 다른 번호로 보이면 대화가 이어지지 않는다."""
    _login_as(client, A)
    post = _write(client)

    _login_as(client, B)
    client.post(f"/community/posts/{post['id']}/comments", json={"body": "첫 댓글"})
    detail = client.post(
        f"/community/posts/{post['id']}/comments", json={"body": "두번째 댓글"}
    ).json()

    labels = [c["author_label"] for c in detail["comments"]]
    assert labels == ["익명1", "익명1"], labels


def test_different_commenters_get_different_numbers(client, boards):
    _login_as(client, A)
    post = _write(client)
    client.post(f"/community/posts/{post['id']}/comments", json={"body": "글쓴이 댓글"})

    _login_as(client, B)
    detail = client.post(
        f"/community/posts/{post['id']}/comments", json={"body": "다른 사람"}
    ).json()

    labels = [c["author_label"] for c in detail["comments"]]
    # 글쓴이 본인은 번호 대신 '글쓴이'로 구분된다
    assert labels == ["글쓴이", "익명1"], labels


def test_anon_numbers_do_not_carry_across_posts(client, boards):
    """다른 글에서 번호가 이어지면 동일인임이 드러난다."""
    _login_as(client, A)
    first = _write(client, title="첫 글")
    second = _write(client, title="둘째 글")

    _login_as(client, B)
    client.post(f"/community/posts/{first['id']}/comments", json={"body": "x"})
    d2 = client.post(
        f"/community/posts/{second['id']}/comments", json={"body": "y"}
    ).json()

    # 둘째 글에서도 다시 1번부터 시작해야 한다
    assert d2["comments"][0]["author_label"] == "익명1"


def test_board_can_force_anonymous(client, boards):
    """비밀게시판에 실명으로 쓰이면 게시판의 존재 이유가 사라진다."""
    _login_as(client, A)
    client.put("/auth/profile", json={"nickname": "앨리스"})
    post = _write(client, slug="secret", is_anonymous=False)
    assert post["author_label"] == "익명"


def test_board_can_forbid_anonymous(client, boards):
    """홍보게시판은 실명이어야 책임 소재가 남는다."""
    _login_as(client, A)
    client.put("/auth/profile", json={"nickname": "앨리스"})
    post = _write(client, slug="promo", is_anonymous=True)
    assert post["author_label"] == "앨리스"


# ---------------- 게시판 목록 ----------------
def test_board_list_and_category_filter(client, boards):
    _login_as(client, A)
    all_boards = client.get("/community/boards").json()
    assert len(all_boards) == 9

    career = client.get("/community/boards", params={"category": "career"}).json()
    assert {b["slug"] for b in career} == {"career"}


def test_board_search(client, boards):
    _login_as(client, A)
    found = client.get("/community/boards", params={"q": "절약"}).json()
    assert [b["slug"] for b in found] == ["saving-tips"]


def test_new_badge_appears_and_clears(client, boards):
    """'N' 뱃지: 마지막으로 읽은 뒤 새 글이 있으면 표시된다."""
    _login_as(client, A)
    _write(client, slug="free")

    _login_as(client, B)
    before = {b["slug"]: b["has_new"] for b in client.get("/community/boards").json()}
    assert before["free"] is True
    assert before["secret"] is False   # 글이 없는 게시판

    client.get("/community/boards/free/posts")   # 읽음 처리
    after = {b["slug"]: b["has_new"] for b in client.get("/community/boards").json()}
    assert after["free"] is False


# ---------------- 글 목록 ----------------
def test_posts_are_newest_first(client, boards):
    _login_as(client, A)
    for i in range(3):
        _write(client, title=f"글{i}")

    items = client.get("/community/boards/free/posts").json()["items"]
    assert [p["title"] for p in items] == ["글2", "글1", "글0"]


def test_post_list_is_paginated(client, boards):
    _login_as(client, A)
    for i in range(25):
        _write(client, title=f"글{i}")

    page = client.get(
        "/community/boards/free/posts", params={"offset": 0, "limit": 10}
    ).json()
    assert page["total"] == 25
    assert len(page["items"]) == 10


def test_preview_is_truncated(client, boards):
    _login_as(client, A)
    post = _write(client, body="가" * 500)
    items = client.get("/community/boards/free/posts").json()["items"]
    assert items[0]["preview"].endswith("…")
    assert len(items[0]["preview"]) <= 121


def test_questions_are_listed_separately(client, boards):
    _login_as(client, A)
    _write(client, title="일반글")
    _write(client, title="질문글", is_question=True)

    questions = client.get("/community/boards/free/questions").json()
    assert [q["title"] for q in questions] == ["질문글"]


def test_unknown_board_returns_404(client, boards):
    _login_as(client, A)
    assert client.get("/community/boards/nope/posts").status_code == 404


# ---------------- 공감 · 스크랩 ----------------
def test_like_toggles_and_counts_once_per_user(client, boards):
    _login_as(client, A)
    post = _write(client)
    pid = post["id"]

    first = client.post(f"/community/posts/{pid}/like").json()
    assert first == {"active": True, "count": 1}

    # 같은 사람이 또 눌러도 늘지 않고 취소된다
    second = client.post(f"/community/posts/{pid}/like").json()
    assert second == {"active": False, "count": 0}


def test_like_count_accumulates_across_users(client, boards):
    _login_as(client, A)
    pid = _write(client)["id"]
    client.post(f"/community/posts/{pid}/like")

    _login_as(client, B)
    result = client.post(f"/community/posts/{pid}/like").json()
    assert result == {"active": True, "count": 2}


def test_liked_by_me_is_per_user(client, boards):
    _login_as(client, A)
    pid = _write(client)["id"]
    client.post(f"/community/posts/{pid}/like")
    assert client.get(f"/community/posts/{pid}").json()["liked_by_me"] is True

    _login_as(client, B)
    assert client.get(f"/community/posts/{pid}").json()["liked_by_me"] is False


def test_scrap_toggles(client, boards):
    _login_as(client, A)
    pid = _write(client)["id"]

    assert client.post(f"/community/posts/{pid}/scrap").json()["active"] is True
    assert client.get(f"/community/posts/{pid}").json()["scrapped_by_me"] is True
    assert client.post(f"/community/posts/{pid}/scrap").json()["active"] is False


# ---------------- 댓글 ----------------
def test_comment_increments_count(client, boards):
    _login_as(client, A)
    pid = _write(client)["id"]

    detail = client.post(
        f"/community/posts/{pid}/comments", json={"body": "댓글"}
    ).json()
    assert detail["comment_count"] == 1
    assert len(detail["comments"]) == 1


def test_reply_to_comment(client, boards):
    _login_as(client, A)
    pid = _write(client)["id"]
    detail = client.post(f"/community/posts/{pid}/comments", json={"body": "부모"}).json()
    parent_id = detail["comments"][0]["id"]

    detail = client.post(
        f"/community/posts/{pid}/comments",
        json={"body": "대댓글", "parent_id": parent_id},
    ).json()
    assert detail["comments"][1]["parent_id"] == parent_id


def test_reply_depth_is_limited_to_one(client, boards):
    """깊이가 늘면 화면에서 읽기 어렵다."""
    _login_as(client, A)
    pid = _write(client)["id"]
    d = client.post(f"/community/posts/{pid}/comments", json={"body": "부모"}).json()
    parent = d["comments"][0]["id"]
    d = client.post(
        f"/community/posts/{pid}/comments", json={"body": "자식", "parent_id": parent}
    ).json()
    child = d["comments"][1]["id"]

    r = client.post(
        f"/community/posts/{pid}/comments", json={"body": "손자", "parent_id": child}
    )
    assert r.status_code == 422


def test_deleted_comment_keeps_thread_readable(client, boards):
    """댓글을 지웠다고 대화 흐름이 사라지면 남은 댓글을 읽을 수 없다."""
    _login_as(client, A)
    pid = _write(client)["id"]
    d = client.post(f"/community/posts/{pid}/comments", json={"body": "지울 댓글"}).json()
    cid = d["comments"][0]["id"]
    client.post(f"/community/posts/{pid}/comments", json={"body": "남을 댓글"})

    assert client.delete(f"/community/comments/{cid}").status_code == 204

    detail = client.get(f"/community/posts/{pid}").json()
    assert detail["comments"][0]["is_deleted"] is True
    assert detail["comments"][0]["body"] == "삭제된 댓글입니다."
    assert detail["comments"][1]["body"] == "남을 댓글"
    assert detail["comment_count"] == 1


def test_cannot_delete_others_comment(client, boards):
    _login_as(client, A)
    pid = _write(client)["id"]
    d = client.post(f"/community/posts/{pid}/comments", json={"body": "내 댓글"}).json()
    cid = d["comments"][0]["id"]

    _login_as(client, B)
    assert client.delete(f"/community/comments/{cid}").status_code == 404


# ---------------- 글 삭제 ----------------
def test_soft_delete_hides_post_from_list(client, boards):
    _login_as(client, A)
    pid = _write(client)["id"]
    assert client.delete(f"/community/posts/{pid}").status_code == 204

    assert client.get("/community/boards/free/posts").json()["items"] == []
    assert client.get(f"/community/posts/{pid}").status_code == 404


def test_cannot_delete_others_post(client, boards):
    _login_as(client, A)
    pid = _write(client)["id"]

    _login_as(client, B)
    assert client.delete(f"/community/posts/{pid}").status_code == 404

    _login_as(client, A)
    assert client.get(f"/community/posts/{pid}").status_code == 200


# ---------------- HOT / BEST ----------------
def test_hot_requires_like_threshold(client, boards, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "community_hot_like_threshold", 2)
    _login_as(client, A)
    cold = _write(client, title="조용한 글")["id"]
    hot = _write(client, title="인기 글")["id"]

    client.post(f"/community/posts/{hot}/like")
    _login_as(client, B)
    client.post(f"/community/posts/{hot}/like")

    titles = [p["title"] for p in client.get("/community/hot").json()["items"]]
    assert titles == ["인기 글"]
    assert "조용한 글" not in titles


def test_best_is_sorted_by_likes(client, boards, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "community_best_like_threshold", 1)
    _login_as(client, A)
    low = _write(client, title="공감1")["id"]
    high = _write(client, title="공감2")["id"]
    client.post(f"/community/posts/{low}/like")
    client.post(f"/community/posts/{high}/like")

    _login_as(client, B)
    client.post(f"/community/posts/{high}/like")

    titles = [p["title"] for p in client.get("/community/best").json()["items"]]
    assert titles == ["공감2", "공감1"]


# ---------------- 내 활동 ----------------
def test_my_posts_includes_anonymous_ones(client, boards):
    """익명으로 썼어도 본인은 자기 글을 찾을 수 있어야 한다."""
    _login_as(client, A)
    _write(client, title="내 익명글", is_anonymous=True)

    _login_as(client, B)
    _write(client, title="남의 글")

    _login_as(client, A)
    mine = client.get("/community/me/posts").json()["items"]
    assert [p["title"] for p in mine] == ["내 익명글"]
    assert mine[0]["is_mine"] is True


def test_my_commented_lists_posts_i_replied_to(client, boards):
    _login_as(client, A)
    pid = _write(client, title="앨리스 글")["id"]

    _login_as(client, B)
    _write(client, title="밥이 쓴 글")
    client.post(f"/community/posts/{pid}/comments", json={"body": "댓글"})

    commented = client.get("/community/me/commented").json()["items"]
    assert [p["title"] for p in commented] == ["앨리스 글"]


def test_my_scraps(client, boards):
    _login_as(client, A)
    pid = _write(client, title="스크랩할 글")["id"]
    client.post(f"/community/posts/{pid}/scrap")

    scraps = client.get("/community/me/scraps").json()["items"]
    assert [p["title"] for p in scraps] == ["스크랩할 글"]


# ---------------- 신고 ----------------
def test_report_is_recorded_once_per_user(client, boards, db):
    from app.models.community import Report

    _login_as(client, A)
    pid = _write(client)["id"]

    _login_as(client, B)
    assert client.post(f"/community/posts/{pid}/report", json={"reason": "욕설"}).status_code == 204
    # 중복 신고로 수치를 부풀릴 수 없어야 한다
    assert client.post(f"/community/posts/{pid}/report", json={"reason": "욕설"}).status_code == 204

    assert db.query(Report).filter(Report.post_id == pid).count() == 1


# ---------------- 인가 ----------------
@pytest.mark.parametrize("method,path,kwargs", [
    ("get", "/community/boards", {}),
    ("get", "/community/boards/free/posts", {}),
    ("get", "/community/hot", {}),
    ("get", "/community/me/posts", {}),
    ("post", "/community/posts", {"json": {"board_slug": "free", "title": "t", "body": "b"}}),
])
def test_community_requires_login(client, boards, method, path, kwargs):
    """익명 글이라도 서버는 작성자를 알아야 신고·차단이 성립한다."""
    r = getattr(client, method)(path, **kwargs)
    assert r.status_code == 401, f"{path} 가 비로그인으로 {r.status_code}"


def test_empty_title_or_body_rejected(client, boards):
    _login_as(client, A)
    assert client.post("/community/posts", json={
        "board_slug": "free", "title": "", "body": "본문"}).status_code == 422
    assert client.post("/community/posts", json={
        "board_slug": "free", "title": "제목", "body": ""}).status_code == 422


# ---------------- 시드 기본값(제품 결정) ----------------
def test_seed_activates_only_saving_boards(client, db):
    """기본 활성 게시판은 절약 꿀팁·공동구매 둘뿐이다.

    자유·비밀·진로 게시판은 에브리타임과 콘텐츠 볼륨으로 경쟁하는 판이라
    끄기로 했다. 지운 게 아니라 is_active 를 내린 것이므로 행은 남는다.
    """
    from sqlalchemy import select

    from app.models.community import Board
    from app.scripts.seed_boards import seed_boards

    seed_boards()
    active = db.scalars(select(Board).where(Board.is_active.is_(True))).all()
    assert {b.slug for b in active} == {"saving-tips", "groupbuy"}
    # 껐을 뿐 삭제하지 않았다
    assert db.scalar(select(Board).where(Board.slug == "secret")) is not None


def test_saving_tips_requires_a_name(client, db):
    """꿀팁이 틀리면 따라한 사람이 돈을 잃는다. 익명으로 못 쓴다."""
    from app.scripts.seed_boards import seed_boards

    seed_boards()
    _login_as(client, A)
    r = client.post(
        "/community/posts",
        json={
            "board_slug": "saving-tips",
            "title": "CU 2+1",
            "body": "회기점에서 되네요",
            "is_anonymous": True,   # 요청해도 게시판 정책이 이긴다
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["author_label"] != "익명"


def test_post_category_filters_the_list(client, boards):
    """게시판이 '목적'이면 카테고리는 '주제'다. 2차원으로 탐색한다."""
    _login_as(client, A)
    _write(client, slug="saving-tips", title="지하철", category="transport")
    _write(client, slug="saving-tips", title="편의점", category="food")

    r = client.get("/community/boards/saving-tips/posts", params={"category": "transport"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [i["title"] for i in items] == ["지하철"]
    assert items[0]["category_label"] == "교통"


def test_named_post_carries_tier_but_anonymous_does_not(client, boards):
    """등급은 별명 글에만 실린다.

    이용자가 적을 때 익명 글에 등급을 붙이면 '이 게시판의 고수는 한 명'이
    되어 익명 번호가 무력화된다.
    """
    _login_as(client, A)
    named = _write(client, slug="saving-tips", title="실명글")
    anon = _write(client, slug="free", title="익명글", is_anonymous=True)

    assert named["author_tier"] is not None
    assert anon["author_tier"] is None


# ---------------- 이미지 ----------------
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def test_post_images_upload_serve_and_cleanup(client, boards, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    _login_as(client, A)
    post = _write(client)

    # 이미지가 아닌 파일은 이름이 .png여도 거절한다(앞머리로 판별).
    r = client.post(
        f"/community/posts/{post['id']}/images",
        files=[("files", ("x.png", b"<svg/>", "image/png"))],
    )
    assert r.status_code == 415

    r = client.post(
        f"/community/posts/{post['id']}/images",
        files=[("files", ("a.png", PNG, "image/png"))],
    )
    assert r.status_code == 200, r.text
    url = r.json()["image_urls"][0]
    assert client.get(url).content == PNG
    listed = client.get("/community/boards/free/posts").json()["items"][0]
    assert listed["thumbnail_url"] == url

    # 남의 글에는 못 붙이고, 글당 4장 제한을 넘지 못한다.
    _login_as(client, B)
    r = client.post(
        f"/community/posts/{post['id']}/images",
        files=[("files", ("a.png", PNG, "image/png"))],
    )
    assert r.status_code == 404

    _login_as(client, A)
    r = client.post(
        f"/community/posts/{post['id']}/images",
        files=[("files", (f"{i}.png", PNG, "image/png")) for i in range(4)],
    )
    assert r.status_code == 400

    # 글을 지우면 파일도 지운다.
    assert client.delete(f"/community/posts/{post['id']}").status_code == 204
    assert client.get(url).status_code == 404


def test_image_route_rejects_path_tricks(client, boards):
    _login_as(client, A)
    assert client.get("/community/images/..%2F..%2Fapp.db").status_code == 404
