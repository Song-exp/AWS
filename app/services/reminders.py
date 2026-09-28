"""마감 리마인더.

새 인프라 없이 이미 있는 부품 세 개를 잇는다:
  Scholarship.deadline_at  ·  services.mailer(smtplib)  ·  services.scheduler

개인화는 기존 매칭 로직을 그대로 쓴다. 조건을 안 보고 전체 공고를 뿌리면
알림이 곧 스팸이 되고, 스팸이 되면 사용자가 알림을 끄고, 알림을 끄면
'몰라서 못 받는' 문제가 그대로 돌아온다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.scholarship import Category, PostingStatus, Scholarship
from app.models.user import User
from app.schemas.schemas import UserProfile
from app.services.mailer import send_deadline_reminder
from app.services.matching import match_scholarships

logger = logging.getLogger(__name__)

#: 매칭 프로필로 옮길 계정 필드
_PROFILE_FIELDS = ("income_bracket", "gpa", "grade_level", "region", "major")


def _days_left(deadline: datetime | None, now: datetime) -> int | None:
    if deadline is None:
        return None
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return (deadline - now).days


def due_postings(db: Session, now: datetime | None = None) -> dict[int, int]:
    """오늘 알릴 공고: {scholarship_id: days_left}.

    D-7/D-3/D-1 처럼 **딱 그날에만** 보낸다. '7일 이하 전부'로 하면 같은
    공고가 이레 내내 온다.
    """
    now = now or datetime.now(timezone.utc)
    targets = set(settings.reminder_day_list)
    if not targets:
        return {}

    rows = db.scalars(
        select(Scholarship).where(
            Scholarship.status.in_([PostingStatus.OPEN, PostingStatus.CLOSING_SOON]),
            Scholarship.deadline_at.is_not(None),
        )
    ).all()

    due: dict[int, int] = {}
    for s in rows:
        left = _days_left(s.deadline_at, now)
        if left is not None and left in targets:
            due[s.id] = left
    return due


def _profile_of(user: User) -> UserProfile:
    return UserProfile(
        **{f: getattr(user, f, None) for f in _PROFILE_FIELDS},
        interests=list(getattr(user, "interests", None) or []),
    )


def send_deadline_reminders(db: Session, now: datetime | None = None) -> int:
    """마감 임박 공고를 대상자에게 메일로 보낸다. 발송한 사용자 수 반환."""
    if not settings.deadline_reminder_enabled:
        return 0

    due = due_postings(db, now)
    if not due:
        return 0

    users = db.scalars(select(User).where(User.email.is_not(None))).all()
    sent = 0
    for user in users:
        if not user.email:
            continue
        matches = match_scholarships(
            db, _profile_of(user), category=Category.SCHOLARSHIP, limit=100
        )
        items = [
            {
                "title": m.scholarship.title,
                "url": m.scholarship.source_url,
                "days_left": due[m.scholarship.id],
            }
            for m in matches
            if m.scholarship.id in due
        ]
        if not items:
            continue
        items.sort(key=lambda i: i["days_left"])
        try:
            send_deadline_reminder(user.email, items)
            sent += 1
        except Exception:  # noqa: BLE001 - 한 명의 발송 실패가 전체를 멈추면 안 된다
            logger.exception("deadline reminder failed for one user")
    return sent
