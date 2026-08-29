"""크롤링 실행 이력 모델.

월간 파이프라인이 실행될 때마다 1건을 기록해 성공/실패·수집 건수·
플랫폼별 리포트를 추적한다(운영 모니터링·디버깅 근거).
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import JSONType, PKType


class CrawlRunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"   # 일부 어댑터 스킵/실패
    FAILED = "failed"


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(PKType, primary_key=True, autoincrement=True)
    trigger: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled|manual

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 이번 실행이 대상으로 삼은 (연,월) 목록. 예: [[2026,8],[2026,9]]
    target_months: Mapped[list] = mapped_column(JSONType, default=list)

    total_fetched: Mapped[int] = mapped_column(Integer, default=0)
    total_saved: Mapped[int] = mapped_column(Integer, default=0)
    total_expired: Mapped[int] = mapped_column(Integer, default=0)

    # 어댑터별 리포트 리스트
    per_platform: Mapped[list] = mapped_column(JSONType, default=list)

    status: Mapped[CrawlRunStatus] = mapped_column(
        Enum(CrawlRunStatus, name="crawl_run_status"), default=CrawlRunStatus.RUNNING
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
