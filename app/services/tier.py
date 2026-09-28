"""절감액 기반 등급.

커뮤니티에서 등급이 하는 일은 자랑이 아니라 **신뢰 표시**다. 익명 아닌
별명 게시판에서 "이 꿀팁을 믿어도 되나"를 판단할 단서가 그 외에 없다.

그래서 두 방향의 힘을 함께 쓴다.
  - 올리는 힘: 누적 절감액(실제로 혜택을 알고 썼다는 증거)
  - 내리는 힘: 내 글에 쌓인 신고(틀린 정보를 올리면 깎인다)

금액 자체는 절대 노출하지 않는다. '47,320원'은 사실상 고유 식별자라
익명성과 무관한 별명 게시판에서도 불필요한 개인정보다. 버킷만 내보낸다.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.community import Post, Report
from app.models.saving import SavingKind, SavingRecord

#: (임계 누적절감액, 라벨). 오름차순.
TIERS: list[tuple[int, str]] = [
    (0, "씨앗"),
    (10_000, "새싹"),
    (50_000, "알뜰"),
    (200_000, "절약러"),
    (500_000, "고수"),
]


class TierOut(BaseModel):
    index: int                 # 0..len(TIERS)-1
    label: str                 # '알뜰'
    next_label: str | None = None
    next_at: int | None = None   # 다음 등급까지 필요한 누적 절감액(원)
    demoted: bool = False        # 신고 누적으로 한 단계 내려갔는지


def tier_index_for(total_saved: float) -> int:
    idx = 0
    for i, (threshold, _) in enumerate(TIERS):
        if total_saved >= threshold:
            idx = i
    return idx


def _report_count_on_my_posts(db: Session, user_id: uuid.UUID) -> int:
    """내가 쓴 글에 쌓인 신고 수. 허위 정보의 대리 지표."""
    return db.scalar(
        select(func.count(Report.id))
        .join(Post, Post.id == Report.post_id)
        .where(Post.author_id == user_id)
    ) or 0


def compute_tier(db: Session, user_id: uuid.UUID) -> TierOut:
    total = db.scalar(
        select(func.coalesce(func.sum(SavingRecord.saved_amount), 0.0)).where(
            SavingRecord.user_id == user_id,
            SavingRecord.kind == SavingKind.SPENT,
        )
    ) or 0.0

    idx = tier_index_for(float(total))

    # 강등: 신고가 임계를 넘으면 한 단계 내린다. 0단계 밑으로는 안 간다.
    demoted = False
    threshold = settings.community_report_demote_threshold
    if threshold > 0 and idx > 0:
        if _report_count_on_my_posts(db, user_id) >= threshold:
            idx -= 1
            demoted = True

    next_label = TIERS[idx + 1][1] if idx + 1 < len(TIERS) else None
    next_at = TIERS[idx + 1][0] if idx + 1 < len(TIERS) else None
    return TierOut(
        index=idx,
        label=TIERS[idx][1],
        next_label=next_label,
        next_at=next_at,
        demoted=demoted,
    )
