"""세이빙 기록 모델(세이빙 대시보드).

기획서 3.3: 안내받은 혜택으로 결제한 뒤 '소비 완료'를 체크하면 절감액이
월간 누적에 반영된다. KPI 두 개가 여기에 직접 걸려 있다.
  - 유저당 월평균 지출 절감액(목표 30,000원)
  - 혜택 조회 후 실소비 전환율(목표 25%)

전환율을 재려면 '조회했다'와 '실제로 썼다'를 모두 남겨야 한다. 그래서
매장 조회 이벤트(VIEWED)와 소비 완료(SPENT)를 같은 테이블에 kind로 구분해
쌓는다. 별도 이벤트 테이블을 두지 않은 이유는 두 값이 항상 같은 분모/분자로
함께 조회되기 때문이다.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import GUIDType, PKType
from app.models.store import SpendCategory


class SavingKind(str, enum.Enum):
    VIEWED = "viewed"   # 지도에서 매장 혜택을 열어봤다(전환율 분모)
    SPENT = "spent"     # 실제로 결제하고 '소비 완료'를 눌렀다(분자)


class SavingRecord(Base):
    """혜택 조회 / 소비 완료 이벤트 한 건."""

    __tablename__ = "saving_records"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUIDType, index=True)

    kind: Mapped[SavingKind] = mapped_column(
        Enum(SavingKind, name="saving_kind"), default=SavingKind.SPENT, index=True
    )

    # 지출 분야. 매장 결제면 업종에서 유도하고, 교통·구독·지원금처럼 매장이
    # 없는 절감은 호출부가 직접 지정한다. 이 컬럼이 없으면 store_id 에 묶여
    # 오프라인 결제만 절감으로 잡힌다.
    category: Mapped[SpendCategory | None] = mapped_column(
        Enum(SpendCategory, name="spend_category"), index=True
    )

    # 매장은 지워질 수 있지만 절감 이력은 남아야 한다(집계가 흔들리면 안 됨).
    # 그래서 FK는 SET NULL 로 두고, 표시용 이름을 스냅샷으로 함께 저장한다.
    store_id: Mapped[int | None] = mapped_column(
        ForeignKey("stores.id", ondelete="SET NULL"), index=True
    )
    store_label: Mapped[str] = mapped_column(String(200), default="")

    # 절감 계산 근거. 나중에 '왜 이만큼 아꼈나'를 사용자에게 보여줄 수 있어야 한다.
    original_amount: Mapped[float] = mapped_column(Float, default=0.0)
    final_amount: Mapped[float] = mapped_column(Float, default=0.0)
    saved_amount: Mapped[float] = mapped_column(Float, default=0.0)
    method_label: Mapped[str] = mapped_column(String(200), default="")

    # server_default=func.now() 를 쓰지 않는다. SQLite의 CURRENT_TIMESTAMP는
    # UTC를 tz 없이 저장하고 PostgreSQL은 서버 타임존을 따라, 방언마다 값이
    # 달라진다. 월간 집계가 9시간씩 밀리는 원인이 되므로 앱이 UTC로 못박는다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        # 월간 집계: user_id + created_at 범위 조회가 주 패턴
        Index("ix_saving_user_created", "user_id", "created_at"),
    )


class UserBenefitCheck(Base):
    """상시 혜택 '켰음' 표시.

    항목 자체는 코드 상수(services/standing_benefits.CATALOG)라 여기엔
    사용자별 상태만 남는다. item_key 는 그 카탈로그의 key 다.
    """

    __tablename__ = "user_benefit_checks"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    item_key: Mapped[str] = mapped_column(String(60), index=True)
    done_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("user_id", "item_key", name="uq_benefit_check_user_item"),
    )
