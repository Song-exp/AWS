"""커뮤니티(게시판) 모델.

기획서 Phase 2의 '절약 꿀팁 공유 커뮤니티'와 '공동구매 게시판'을 담는다.

익명 설계가 이 도메인의 핵심이다. 대학 커뮤니티에서 익명은 부가 기능이
아니라 사람들이 글을 쓰는 이유다. 그래서 두 가지를 지킨다:
  1. 익명 글·댓글은 API 응답에 작성자 id를 절대 싣지 않는다.
  2. 같은 글 안에서 같은 사람은 늘 같은 번호('익명1')로 보인다. 매번 새
     번호를 주면 대화가 이어지지 않고, 전역 번호를 쓰면 다른 글에서
     동일인임이 드러난다. 그래서 번호는 **글 단위**로 부여한다.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.store import SpendCategory
from app.core.types import GUIDType, JSONType, PKType


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BoardCategory(str, enum.Enum):
    """게시판 묶음(상단 칩)."""

    GENERAL = "general"   # 전체 탭에만 나오는 기본 게시판
    CAREER = "career"     # 진로
    PROMO = "promo"       # 홍보
    GROUP = "group"       # 단체


class Board(Base):
    """게시판."""

    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(300))
    category: Mapped[BoardCategory] = mapped_column(
        Enum(BoardCategory, name="board_category"),
        default=BoardCategory.GENERAL,
        index=True,
    )
    # 익명 글쓰기 정책. 게시판 성격에 따라 다르다
    # (비밀게시판은 익명 강제, 홍보게시판은 실명만).
    allows_anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    forces_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Post(Base):
    """게시글."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), index=True
    )
    # 작성자가 탈퇴해도 글과 댓글 흐름은 남아야 한다(대화가 끊기면 읽을 수 없다).
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        GUIDType, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    # 지출 분야 태그. 게시판이 '글의 목적'(꿀팁/공동구매)이라면 이쪽은
    # '글의 주제'(교통/식비/...)다. 게시판 2개 × 카테고리 7개로 탐색한다.
    category: Mapped[SpendCategory | None] = mapped_column(
        Enum(SpendCategory, name="spend_category"), index=True
    )
    # 질문글은 목록 상단에 카드로 따로 노출된다.
    is_question: Mapped[bool] = mapped_column(Boolean, default=False)
    # 첨부 이미지의 저장 파일명(uuid.ext). 파일은 settings.upload_dir/community 에 둔다.
    image_names: Mapped[list] = mapped_column(JSONType, default=list)

    # 집계값. 매번 count(*) 하면 목록 조회가 글 수에 비례해 느려진다.
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )
    # 소프트 삭제. 댓글이 달린 글을 통째로 지우면 남의 댓글까지 사라진다.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    board: Mapped["Board"] = relationship()
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # 게시판별 최신순 목록이 주 조회 패턴
        Index("ix_posts_board_created", "board_id", "created_at"),
        # HOT/BEST: 공감수 기준 조회
        Index("ix_posts_like_created", "like_count", "created_at"),
    )


class Comment(Base):
    """댓글. parent_id 가 있으면 대댓글이다."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        GUIDType, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    body: Mapped[str] = mapped_column(Text)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    # 이 글 안에서의 익명 번호('익명1'). 글 단위로 부여해 같은 사람이 같은
    # 글에서는 같은 번호로 보이되, 다른 글에서는 이어지지 않게 한다.
    anon_seq: Mapped[int | None] = mapped_column(Integer)

    like_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    post: Mapped["Post"] = relationship(back_populates="comments")

    __table_args__ = (Index("ix_comments_post_created", "post_id", "created_at"),)


class PostLike(Base):
    """글 공감. 한 사람이 한 번만."""

    __tablename__ = "post_likes"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_post_like"),)


class CommentLike(Base):
    __tablename__ = "comment_likes"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_like"),
    )


class Scrap(Base):
    """스크랩(북마크)."""

    __tablename__ = "scraps"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_scrap"),)


class BoardRead(Base):
    """게시판별 마지막 읽은 시각. 목록의 새글 'N' 뱃지 판정에 쓴다."""

    __tablename__ = "board_reads"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    last_read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    __table_args__ = (UniqueConstraint("board_id", "user_id", name="uq_board_read"),)


class Report(Base):
    """신고. 익명 커뮤니티를 운영하려면 없으면 안 된다."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE")
    )
    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE")
    )
    # 끝난 혜택 제보도 같은 그릇을 쓴다. 중복 방지·집계·관리자 조회가
    # 커뮤니티 신고와 완전히 같은 로직이라 테이블을 나눌 이유가 없다.
    # reason='offer_expired' 로 구분한다.
    store_offer_id: Mapped[int | None] = mapped_column(
        ForeignKey("store_offers.id", ondelete="CASCADE")
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        GUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        UniqueConstraint("post_id", "reporter_id", name="uq_report_post"),
        UniqueConstraint("comment_id", "reporter_id", name="uq_report_comment"),
        UniqueConstraint("store_offer_id", "reporter_id", name="uq_report_offer"),
    )
