"""커뮤니티(게시판) API.

화면 구성(에브리타임류):
  - 게시판 목록: 카테고리 칩 · 검색 · 바로가기(내 글/댓글 단 글/스크랩/HOT/BEST)
  - 글 목록: 질문글 카드 · HOT 글 · 최신 글 목록
  - 글 상세: 공감 · 댓글(대댓글) · 스크랩 · 신고

익명 규칙(이 파일에서 가장 중요한 부분):
  익명 글·댓글은 응답에 author_id 를 절대 싣지 않는다. 표시 이름은
  글 단위 번호('익명1')로 만들고, 글쓴이 본인의 댓글은 '글쓴이'로 보여준다.
  내가 쓴 글인지는 author_id 노출이 아니라 is_mine 플래그로 알린다.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user
from app.models.community import (
    Board,
    BoardCategory,
    BoardRead,
    Comment,
    CommentLike,
    Post,
    PostLike,
    Report,
    Scrap,
)
from app.models.store import SPEND_LABELS, SpendCategory
from app.models.user import User
from app.services.tier import compute_tier
from app.utils.upload import read_limited

router = APIRouter(
    prefix="/community",
    tags=["community"],
    # 커뮤니티는 전부 로그인 사용자만 쓴다. 익명 글이라도 '누가 썼는지'를
    # 서버는 알아야 신고·차단이 성립한다.
    dependencies=[Depends(current_user)],
)

KST = timezone(timedelta(hours=9))


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    aware = _as_utc(dt)
    return aware.astimezone(KST).isoformat() if aware else None


# ---------------- 응답 스키마 ----------------
class BoardOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None = None
    category: str
    allows_anonymous: bool
    forces_anonymous: bool
    has_new: bool = False       # 마지막으로 읽은 뒤 새 글이 있는지('N' 뱃지)


class PostSummaryOut(BaseModel):
    id: int
    board_id: int
    board_name: str
    title: str
    preview: str                # 목록에서 2줄로 보여줄 본문 앞부분
    author_label: str           # '익명' 또는 닉네임
    # 등급은 별명 글에만 싣는다. 익명 글에 붙이면 이용자가 적을 때
    # '이 게시판의 고수는 한 명' → 익명N의 정체가 드러난다.
    author_tier: str | None = None
    category: SpendCategory | None = None
    category_label: str | None = None
    is_question: bool
    like_count: int
    comment_count: int
    created_at: str | None = None
    is_mine: bool = False
    thumbnail_url: str | None = None   # 첫 첨부 이미지(목록 썸네일)


class CommentOut(BaseModel):
    id: int
    parent_id: int | None = None
    body: str
    author_label: str           # '익명1' / '글쓴이' / 닉네임
    like_count: int
    liked_by_me: bool = False
    is_mine: bool = False
    is_deleted: bool = False
    created_at: str | None = None


class PostDetailOut(BaseModel):
    id: int
    board_id: int
    board_name: str
    title: str
    body: str
    author_label: str
    author_tier: str | None = None
    category: SpendCategory | None = None
    category_label: str | None = None
    is_question: bool
    like_count: int
    comment_count: int
    view_count: int
    liked_by_me: bool = False
    scrapped_by_me: bool = False
    is_mine: bool = False
    created_at: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    comments: list[CommentOut] = Field(default_factory=list)


class PostPage(BaseModel):
    items: list[PostSummaryOut]
    total: int
    offset: int
    limit: int


# ---------------- 표시 이름 ----------------
def _author_label(
    author_id, is_anonymous: bool, nickname: str | None, anon_seq: int | None = None
) -> str:
    """익명이면 절대 실명을 만들지 않는다.

    댓글은 글 단위 번호를 붙여 '익명1'처럼 구분한다. 번호가 없으면(글 본문)
    그냥 '익명'이다.
    """
    if is_anonymous or author_id is None:
        return f"익명{anon_seq}" if anon_seq else "익명"
    return nickname or "탈퇴한 사용자"


def _post_author_label(post: Post, nickname: str | None) -> str:
    return _author_label(post.author_id, post.is_anonymous, nickname)


def _preview(body: str, limit: int = 120) -> str:
    text = " ".join((body or "").split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _nickname_map(db: Session, posts: list[Post]) -> dict:
    """실명 글의 닉네임만 미리 읽는다(익명 글은 조회조차 하지 않는다)."""
    ids = {p.author_id for p in posts if not p.is_anonymous and p.author_id}
    if not ids:
        return {}
    rows = db.execute(select(User.id, User.nickname).where(User.id.in_(ids))).all()
    return {uid: nick for uid, nick in rows}


def _tier_map(db: Session, posts: list[Post]) -> dict:
    """별명 글 작성자만 등급을 계산한다.

    익명 글에는 등급을 싣지 않으므로 조회조차 하지 않는다 — 계산 비용이
    아니라 노출 사고를 막기 위한 것이다.
    """
    ids = {p.author_id for p in posts if not p.is_anonymous and p.author_id}
    return {uid: compute_tier(db, uid).label for uid in ids}


def _to_summary(
    db: Session, post: Post, user: User, nicknames: dict, tiers: dict | None = None
) -> PostSummaryOut:
    tiers = tiers or {}
    return PostSummaryOut(
        id=post.id,
        board_id=post.board_id,
        board_name=post.board.name,
        title=post.title,
        preview=_preview(post.body),
        author_label=_post_author_label(post, nicknames.get(post.author_id)),
        author_tier=None if post.is_anonymous else tiers.get(post.author_id),
        category=post.category,
        category_label=SPEND_LABELS.get(post.category) if post.category else None,
        is_question=post.is_question,
        like_count=post.like_count,
        comment_count=post.comment_count,
        created_at=_iso(post.created_at),
        is_mine=post.author_id == user.id,
        thumbnail_url=_image_url(post.image_names[0]) if post.image_names else None,
    )


def _page(db: Session, stmt, user: User, offset: int, limit: int) -> PostPage:
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    posts = db.scalars(stmt.offset(offset).limit(limit)).all()
    nicknames = _nickname_map(db, list(posts))
    tiers = _tier_map(db, list(posts))
    return PostPage(
        items=[_to_summary(db, p, user, nicknames, tiers) for p in posts],
        total=total,
        offset=offset,
        limit=limit,
    )


def _visible_posts():
    """삭제된 글은 목록에서 제외한다."""
    return select(Post).where(Post.deleted_at.is_(None))


# ---------------- 게시판 ----------------
@router.get("/boards", response_model=list[BoardOut])
def list_boards(
    category: BoardCategory | None = Query(default=None, description="상단 칩 필터"),
    q: str | None = Query(default=None, description="게시판 이름 검색"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[BoardOut]:
    """게시판 목록. 마지막 읽은 시각과 비교해 새 글 여부를 함께 준다."""
    stmt = select(Board).where(Board.is_active.is_(True))
    if category:
        stmt = stmt.where(Board.category == category)
    if q:
        stmt = stmt.where(Board.name.ilike(f"%{q.strip()}%"))
    boards = db.scalars(stmt.order_by(Board.sort_order, Board.id)).all()

    reads = {
        r.board_id: _as_utc(r.last_read_at)
        for r in db.scalars(select(BoardRead).where(BoardRead.user_id == user.id)).all()
    }
    # 게시판마다 최신 글 시각을 한 번에 읽는다(게시판 수만큼 질의하지 않기 위해).
    latest = dict(
        db.execute(
            select(Post.board_id, func.max(Post.created_at))
            .where(Post.deleted_at.is_(None))
            .group_by(Post.board_id)
        ).all()
    )

    out: list[BoardOut] = []
    for b in boards:
        newest = _as_utc(latest.get(b.id))
        last_read = reads.get(b.id)
        # 한 번도 안 읽었으면 글이 하나라도 있으면 새 글로 본다.
        has_new = bool(newest) and (last_read is None or newest > last_read)
        out.append(
            BoardOut(
                id=b.id,
                slug=b.slug,
                name=b.name,
                description=b.description,
                category=b.category.value,
                allows_anonymous=b.allows_anonymous,
                forces_anonymous=b.forces_anonymous,
                has_new=has_new,
            )
        )
    return out


@router.get("/boards/{slug}/posts", response_model=PostPage)
def list_board_posts(
    slug: str,
    category: list[SpendCategory] | None = Query(
        default=None, description="지출 분야 칩 필터(복수 가능)"
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PostPage:
    """게시판의 글 목록(최신순). 조회 시점을 읽음으로 기록한다."""
    board = db.scalar(select(Board).where(Board.slug == slug))
    if board is None:
        raise HTTPException(404, "게시판을 찾을 수 없습니다.")

    row = db.scalar(
        select(BoardRead).where(
            BoardRead.board_id == board.id, BoardRead.user_id == user.id
        )
    )
    if row is None:
        db.add(BoardRead(board_id=board.id, user_id=user.id))
    else:
        row.last_read_at = datetime.now(timezone.utc)
    db.commit()

    stmt = _visible_posts().where(Post.board_id == board.id)
    if category:
        stmt = stmt.where(Post.category.in_(category))
    stmt = stmt.order_by(Post.created_at.desc(), Post.id.desc())
    return _page(db, stmt, user, offset, limit)


@router.get("/boards/{slug}/questions", response_model=list[PostSummaryOut])
def list_questions(
    slug: str,
    limit: int = Query(default=5, ge=1, le=20),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[PostSummaryOut]:
    """목록 상단의 질문글 카드."""
    board = db.scalar(select(Board).where(Board.slug == slug))
    if board is None:
        raise HTTPException(404, "게시판을 찾을 수 없습니다.")

    posts = db.scalars(
        _visible_posts()
        .where(Post.board_id == board.id, Post.is_question.is_(True))
        .order_by(Post.created_at.desc())
        .limit(limit)
    ).all()
    nicknames = _nickname_map(db, list(posts))
    tiers = _tier_map(db, list(posts))
    return [_to_summary(db, p, user, nicknames, tiers) for p in posts]


# ---------------- HOT / BEST ----------------
@router.get("/hot", response_model=PostPage)
def hot_posts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PostPage:
    """공감이 일정 수를 넘은 글."""
    stmt = (
        _visible_posts()
        .where(Post.like_count >= settings.community_hot_like_threshold)
        .order_by(Post.created_at.desc())
    )
    return _page(db, stmt, user, offset, limit)


@router.get("/best", response_model=PostPage)
def best_posts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PostPage:
    """HOT 보다 높은 기준을 넘은 글. 공감순으로 정렬한다."""
    stmt = (
        _visible_posts()
        .where(Post.like_count >= settings.community_best_like_threshold)
        .order_by(Post.like_count.desc(), Post.created_at.desc())
    )
    return _page(db, stmt, user, offset, limit)


# ---------------- 내 활동 ----------------
@router.get("/me/posts", response_model=PostPage)
def my_posts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PostPage:
    """내가 쓴 글. 익명으로 썼어도 본인에게는 보여야 한다."""
    stmt = (
        _visible_posts()
        .where(Post.author_id == user.id)
        .order_by(Post.created_at.desc())
    )
    return _page(db, stmt, user, offset, limit)


@router.get("/me/commented", response_model=PostPage)
def my_commented_posts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PostPage:
    """내가 댓글 단 글."""
    commented = (
        select(Comment.post_id)
        .where(Comment.author_id == user.id, Comment.deleted_at.is_(None))
        .distinct()
    )
    stmt = (
        _visible_posts()
        .where(Post.id.in_(commented))
        .order_by(Post.created_at.desc())
    )
    return _page(db, stmt, user, offset, limit)


@router.get("/me/scraps", response_model=PostPage)
def my_scraps(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PostPage:
    scrapped = select(Scrap.post_id).where(Scrap.user_id == user.id)
    stmt = (
        _visible_posts()
        .where(Post.id.in_(scrapped))
        .order_by(Post.created_at.desc())
    )
    return _page(db, stmt, user, offset, limit)


# ---------------- 글 ----------------
class PostCreateIn(BaseModel):
    board_slug: str
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    is_anonymous: bool = True
    is_question: bool = False
    # 게시판이 '글의 목적'이라면 카테고리는 '글의 주제'다. 게시판 2개로
    # 줄인 대신 이 축으로 탐색한다.
    category: SpendCategory | None = None


@router.post("/posts", response_model=PostDetailOut, status_code=201)
def create_post(
    payload: PostCreateIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PostDetailOut:
    board = db.scalar(select(Board).where(Board.slug == payload.board_slug))
    if board is None or not board.is_active:
        raise HTTPException(404, "게시판을 찾을 수 없습니다.")

    # 게시판 정책이 사용자의 선택보다 우선한다. 비밀게시판에 실명으로 쓰이거나
    # 홍보게시판에 익명으로 쓰이면 게시판의 존재 이유가 사라진다.
    anonymous = payload.is_anonymous
    if board.forces_anonymous:
        anonymous = True
    elif not board.allows_anonymous:
        anonymous = False

    post = Post(
        board_id=board.id,
        author_id=user.id,
        title=payload.title.strip(),
        body=payload.body.strip(),
        is_anonymous=anonymous,
        is_question=payload.is_question,
        category=payload.category,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _post_detail(db, post, user)


@router.get("/posts/{post_id}", response_model=PostDetailOut)
def read_post(
    post_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PostDetailOut:
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(404, "글을 찾을 수 없습니다.")
    post.view_count += 1
    db.commit()
    return _post_detail(db, post, user)


@router.delete("/posts/{post_id}", status_code=204, response_class=Response)
def delete_post(
    post_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """소프트 삭제. 남의 댓글까지 사라지지 않게 한다."""
    post = db.get(Post, post_id)
    # 없는 글과 남의 글을 같은 404로 응답해 존재 여부를 흘리지 않는다.
    if post is None or post.deleted_at is not None or post.author_id != user.id:
        raise HTTPException(404, "글을 찾을 수 없습니다.")
    post.deleted_at = datetime.now(timezone.utc)
    names, post.image_names = post.image_names or [], []
    db.commit()
    for name in names:
        _image_path(name).unlink(missing_ok=True)
    return Response(status_code=204)


# ---------------- 첨부 이미지 ----------------
MAX_IMAGES_PER_POST = 4
# 확장자는 클라이언트가 준 이름이 아니라 파일 앞머리(매직 바이트)로 정한다.
_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)
_IMAGE_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|gif|webp)$")


def _sniff_image(head: bytes) -> str | None:
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return next((ext for sig, ext in _IMAGE_SIGNATURES if head.startswith(sig)), None)


def _image_dir():
    from pathlib import Path

    return Path(settings.upload_dir) / "community"


def _image_path(name: str):
    return _image_dir() / name


def _image_url(name: str) -> str:
    # 프론트가 API_BASE를 앞에 붙인다(배포 경로가 바뀌어도 백엔드는 모른다).
    return f"/community/images/{name}"


@router.post("/posts/{post_id}/images", response_model=PostDetailOut)
async def upload_post_images(
    post_id: int,
    files: list[UploadFile] = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PostDetailOut:
    """내 글에 이미지를 붙인다. 글을 먼저 만든 뒤 호출한다."""
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None or post.author_id != user.id:
        raise HTTPException(404, "글을 찾을 수 없습니다.")
    existing = list(post.image_names or [])
    if len(existing) + len(files) > MAX_IMAGES_PER_POST:
        raise HTTPException(400, f"이미지는 글당 {MAX_IMAGES_PER_POST}장까지 올릴 수 있어요.")

    # 전부 검사한 뒤에 저장한다. 중간에 실패하면 반쪽만 붙지 않게.
    staged: list[tuple[str, bytes]] = []
    for f in files:
        content = await read_limited(
            f, f"이미지가 너무 큽니다(최대 {settings.max_upload_mb}MB)."
        )
        ext = _sniff_image(content[:16])
        if ext is None:
            raise HTTPException(415, "JPG·PNG·GIF·WEBP 이미지만 올릴 수 있어요.")
        staged.append((f"{uuid.uuid4().hex}.{ext}", content))

    os.makedirs(_image_dir(), exist_ok=True)
    for name, content in staged:
        _image_path(name).write_bytes(content)
    post.image_names = existing + [name for name, _ in staged]
    db.commit()
    db.refresh(post)
    return _post_detail(db, post, user)


@router.get("/images/{name}")
def read_post_image(name: str) -> FileResponse:
    # 이름 형식을 강제해 경로 조작(../)을 막는다.
    if not _IMAGE_NAME.match(name) or not _image_path(name).is_file():
        raise HTTPException(404, "이미지를 찾을 수 없습니다.")
    return FileResponse(_image_path(name))


def _post_detail(db: Session, post: Post, user: User) -> PostDetailOut:
    nickname = None
    if not post.is_anonymous and post.author_id:
        nickname = db.scalar(select(User.nickname).where(User.id == post.author_id))

    comments = db.scalars(
        select(Comment)
        .where(Comment.post_id == post.id)
        .order_by(Comment.created_at, Comment.id)
    ).all()

    liked_comment_ids = set()
    if comments:
        liked_comment_ids = set(
            db.scalars(
                select(CommentLike.comment_id).where(
                    CommentLike.user_id == user.id,
                    CommentLike.comment_id.in_([c.id for c in comments]),
                )
            ).all()
        )

    comment_nicknames: dict = {}
    named_ids = {c.author_id for c in comments if not c.is_anonymous and c.author_id}
    if named_ids:
        comment_nicknames = {
            uid: nick
            for uid, nick in db.execute(
                select(User.id, User.nickname).where(User.id.in_(named_ids))
            ).all()
        }

    comment_out: list[CommentOut] = []
    for c in comments:
        deleted = c.deleted_at is not None
        if c.is_anonymous and c.author_id and c.author_id == post.author_id:
            # 글쓴이 본인의 댓글은 번호 대신 '글쓴이'로 표시한다.
            label = "글쓴이"
        else:
            label = _author_label(
                c.author_id, c.is_anonymous, comment_nicknames.get(c.author_id), c.anon_seq
            )
        comment_out.append(
            CommentOut(
                id=c.id,
                parent_id=c.parent_id,
                body="삭제된 댓글입니다." if deleted else c.body,
                author_label=label,
                like_count=c.like_count,
                liked_by_me=c.id in liked_comment_ids,
                is_mine=(not deleted) and c.author_id == user.id,
                is_deleted=deleted,
                created_at=_iso(c.created_at),
            )
        )

    liked = db.scalar(
        select(PostLike).where(PostLike.post_id == post.id, PostLike.user_id == user.id)
    )
    scrapped = db.scalar(
        select(Scrap).where(Scrap.post_id == post.id, Scrap.user_id == user.id)
    )

    return PostDetailOut(
        id=post.id,
        board_id=post.board_id,
        board_name=post.board.name,
        title=post.title,
        body=post.body,
        author_label=_post_author_label(post, nickname),
        author_tier=(
            None
            if post.is_anonymous or not post.author_id
            else compute_tier(db, post.author_id).label
        ),
        category=post.category,
        category_label=SPEND_LABELS.get(post.category) if post.category else None,
        is_question=post.is_question,
        like_count=post.like_count,
        comment_count=post.comment_count,
        view_count=post.view_count,
        liked_by_me=liked is not None,
        scrapped_by_me=scrapped is not None,
        is_mine=post.author_id == user.id,
        created_at=_iso(post.created_at),
        image_urls=[_image_url(name) for name in post.image_names or []],
        comments=comment_out,
    )


# ---------------- 댓글 ----------------
class CommentCreateIn(BaseModel):
    body: str = Field(min_length=1, max_length=3000)
    is_anonymous: bool = True
    parent_id: int | None = None


def _next_anon_seq(db: Session, post: Post, author_id) -> int | None:
    """이 글에서 이 사람의 익명 번호. 이미 쓴 적 있으면 그 번호를 재사용한다.

    같은 사람이 댓글마다 다른 번호로 보이면 대화가 이어지지 않는다.

    글쓴이 본인은 번호를 받지 않는다. 화면에 '글쓴이'로 표시되므로 번호를
    소비하면 다른 사람이 익명2부터 시작해 1번이 비어 보인다.
    """
    if author_id == post.author_id:
        return None

    existing = db.scalar(
        select(Comment.anon_seq).where(
            Comment.post_id == post.id,
            Comment.author_id == author_id,
            Comment.anon_seq.is_not(None),
        )
    )
    if existing:
        return existing
    used = db.scalar(
        select(func.max(Comment.anon_seq)).where(Comment.post_id == post.id)
    )
    return (used or 0) + 1


@router.post("/posts/{post_id}/comments", response_model=PostDetailOut, status_code=201)
def create_comment(
    post_id: int,
    payload: CommentCreateIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PostDetailOut:
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(404, "글을 찾을 수 없습니다.")

    if payload.parent_id is not None:
        parent = db.get(Comment, payload.parent_id)
        if parent is None or parent.post_id != post.id:
            raise HTTPException(404, "댓글을 찾을 수 없습니다.")
        if parent.parent_id is not None:
            # 대댓글의 대댓글은 받지 않는다. 깊이가 늘면 화면에서 읽기 어렵다.
            raise HTTPException(422, "대댓글에는 답글을 달 수 없습니다.")

    board = post.board
    anonymous = payload.is_anonymous
    if board.forces_anonymous:
        anonymous = True
    elif not board.allows_anonymous:
        anonymous = False

    comment = Comment(
        post_id=post.id,
        parent_id=payload.parent_id,
        author_id=user.id,
        body=payload.body.strip(),
        is_anonymous=anonymous,
        anon_seq=_next_anon_seq(db, post, user.id) if anonymous else None,
    )
    db.add(comment)
    post.comment_count += 1
    db.commit()
    db.refresh(post)
    return _post_detail(db, post, user)


@router.delete("/comments/{comment_id}", status_code=204, response_class=Response)
def delete_comment(
    comment_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    comment = db.get(Comment, comment_id)
    if comment is None or comment.deleted_at is not None or comment.author_id != user.id:
        raise HTTPException(404, "댓글을 찾을 수 없습니다.")
    comment.deleted_at = datetime.now(timezone.utc)
    post = db.get(Post, comment.post_id)
    if post and post.comment_count > 0:
        post.comment_count -= 1
    db.commit()
    return Response(status_code=204)


# ---------------- 공감 · 스크랩 ----------------
class ToggleOut(BaseModel):
    active: bool
    count: int


@router.post("/posts/{post_id}/like", response_model=ToggleOut)
def toggle_post_like(
    post_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ToggleOut:
    """공감 토글. 같은 사람이 여러 번 눌러도 1로 유지된다."""
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(404, "글을 찾을 수 없습니다.")

    row = db.scalar(
        select(PostLike).where(PostLike.post_id == post.id, PostLike.user_id == user.id)
    )
    if row:
        db.delete(row)
        post.like_count = max(0, post.like_count - 1)
        active = False
    else:
        db.add(PostLike(post_id=post.id, user_id=user.id))
        post.like_count += 1
        active = True
    db.commit()
    return ToggleOut(active=active, count=post.like_count)


@router.post("/comments/{comment_id}/like", response_model=ToggleOut)
def toggle_comment_like(
    comment_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ToggleOut:
    comment = db.get(Comment, comment_id)
    if comment is None or comment.deleted_at is not None:
        raise HTTPException(404, "댓글을 찾을 수 없습니다.")

    row = db.scalar(
        select(CommentLike).where(
            CommentLike.comment_id == comment.id, CommentLike.user_id == user.id
        )
    )
    if row:
        db.delete(row)
        comment.like_count = max(0, comment.like_count - 1)
        active = False
    else:
        db.add(CommentLike(comment_id=comment.id, user_id=user.id))
        comment.like_count += 1
        active = True
    db.commit()
    return ToggleOut(active=active, count=comment.like_count)


@router.post("/posts/{post_id}/scrap", response_model=ToggleOut)
def toggle_scrap(
    post_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ToggleOut:
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(404, "글을 찾을 수 없습니다.")

    row = db.scalar(
        select(Scrap).where(Scrap.post_id == post.id, Scrap.user_id == user.id)
    )
    if row:
        db.delete(row)
        active = False
    else:
        db.add(Scrap(post_id=post.id, user_id=user.id))
        active = True
    db.commit()
    count = db.scalar(
        select(func.count()).select_from(Scrap).where(Scrap.post_id == post.id)
    )
    return ToggleOut(active=active, count=count or 0)


# ---------------- 신고 ----------------
class ReportIn(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


@router.post("/posts/{post_id}/report", status_code=204, response_class=Response)
def report_post(
    post_id: int,
    payload: ReportIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(404, "글을 찾을 수 없습니다.")
    existing = db.scalar(
        select(Report).where(Report.post_id == post.id, Report.reporter_id == user.id)
    )
    # 같은 사람이 여러 번 신고해도 한 건으로 본다(중복 신고로 수치를 부풀리지 못하게).
    if existing is None:
        db.add(
            Report(post_id=post.id, reporter_id=user.id, reason=payload.reason.strip())
        )
        db.commit()
    return Response(status_code=204)


@router.post("/comments/{comment_id}/report", status_code=204, response_class=Response)
def report_comment(
    comment_id: int,
    payload: ReportIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    comment = db.get(Comment, comment_id)
    if comment is None or comment.deleted_at is not None:
        raise HTTPException(404, "댓글을 찾을 수 없습니다.")
    existing = db.scalar(
        select(Report).where(
            Report.comment_id == comment.id, Report.reporter_id == user.id
        )
    )
    if existing is None:
        db.add(
            Report(
                comment_id=comment.id,
                reporter_id=user.id,
                reason=payload.reason.strip(),
            )
        )
        db.commit()
    return Response(status_code=204)
