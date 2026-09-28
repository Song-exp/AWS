"""상시 혜택 API(혜택 탭의 '상시' 섹션).

공고와 정렬·수명 규칙이 다르다. 마감이 없어 시간순으로 두면 영원히 목록
바닥에 깔리므로 **절감액 추정치 순**으로 내려보내고, 상태는 '켰나/안 켰나'
하나뿐이라 토글로 끝난다.

목록 자체는 비로그인도 볼 수 있다. 뭘 받을 수 있는지 보려고 가입부터
하라고 하면 아무도 안 본다. 체크는 계정에 남으므로 로그인이 필요하다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, optional_user
from app.models.saving import UserBenefitCheck
from app.models.store import SPEND_LABELS, SpendCategory
from app.models.user import User
from app.services.standing_benefits import BY_KEY, CATALOG

router = APIRouter(prefix="/benefits", tags=["benefits"])


class BenefitItemOut(BaseModel):
    key: str
    title: str
    category: SpendCategory
    category_label: str
    summary: str
    saving_hint_krw: int
    effort_min: int
    credential: str | None = None
    url: str | None = None
    search_hint: str | None = None
    done: bool = False


class BenefitItemsOut(BaseModel):
    items: list[BenefitItemOut]
    #: 아직 안 켠 항목의 연 절감액 추정 합계. 화면 상단 한 줄이 된다.
    remaining_hint_krw: int
    remaining_count: int


class ToggleOut(BaseModel):
    active: bool
    count: int


def _checked_keys(db: Session, user: User | None) -> set[str]:
    if user is None:
        return set()
    rows = db.scalars(
        select(UserBenefitCheck.item_key).where(UserBenefitCheck.user_id == user.id)
    ).all()
    return set(rows)


@router.get("/items", response_model=BenefitItemsOut)
def list_items(
    category: list[SpendCategory] | None = Query(default=None),
    undone_only: bool = Query(default=False, description="안 켠 것만"),
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> BenefitItemsOut:
    """상시 혜택 목록. 절감액 추정치 큰 순."""
    done = _checked_keys(db, user)

    items: list[BenefitItemOut] = []
    for raw in CATALOG:
        if category and raw["category"] not in category:
            continue
        is_done = raw["key"] in done
        if undone_only and is_done:
            continue
        items.append(
            BenefitItemOut(
                **{k: v for k, v in raw.items() if k != "category"},
                category=raw["category"],
                category_label=SPEND_LABELS[raw["category"]],
                done=is_done,
            )
        )
    items.sort(key=lambda i: (i.done, -i.saving_hint_krw))

    remaining = [i for i in items if not i.done]
    return BenefitItemsOut(
        items=items,
        remaining_hint_krw=sum(i.saving_hint_krw for i in remaining),
        remaining_count=len(remaining),
    )


@router.post("/items/{item_key}/check", response_model=ToggleOut)
def toggle_check(
    item_key: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ToggleOut:
    """'챙겼음' 토글. 다시 누르면 해제된다(오탭 복구)."""
    if item_key not in BY_KEY:
        raise HTTPException(404, "없는 혜택 항목입니다.")

    row = db.scalar(
        select(UserBenefitCheck).where(
            UserBenefitCheck.user_id == user.id,
            UserBenefitCheck.item_key == item_key,
        )
    )
    if row is None:
        db.add(UserBenefitCheck(user_id=user.id, item_key=item_key))
        active = True
    else:
        db.delete(row)
        active = False
    db.commit()

    done = _checked_keys(db, user)
    return ToggleOut(active=active, count=len(done))
