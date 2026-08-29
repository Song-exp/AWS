"""월간 크롤 스케줄러(APScheduler).

매월 지정일(기본 1일) 04:00 KST에 run_monthly_update를 실행한다.
FastAPI lifespan에서 start/shutdown 한다. 설정으로 on/off.
"""
from __future__ import annotations

import logging
from datetime import timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.db import SessionLocal
from app.crawlers.registry import run_monthly_update

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_JOB_ID = "monthly_crawl_update"

_scheduler: BackgroundScheduler | None = None


def _scheduled_job() -> None:
    """스케줄러가 호출하는 작업. 자체 DB 세션을 열고 닫는다."""
    db = SessionLocal()
    try:
        run = run_monthly_update(db, trigger="scheduled")
        logger.info(
            "monthly crawl done: run_id=%s status=%s saved=%s expired=%s",
            run.id, run.status, run.total_saved, run.total_expired,
        )
    except Exception:  # noqa: BLE001
        logger.exception("scheduled monthly crawl failed")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    """스케줄러 시작. 비활성화 설정이면 None 반환."""
    global _scheduler
    if not settings.crawl_schedule_enabled:
        logger.info("crawl scheduler disabled by settings")
        return None
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone=KST)
    trigger = CronTrigger(
        day=settings.crawl_schedule_day,
        hour=settings.crawl_schedule_hour,
        minute=settings.crawl_schedule_minute,
        timezone=KST,
    )
    _scheduler.add_job(
        _scheduled_job,
        trigger=trigger,
        id=_JOB_ID,
        replace_existing=True,
        misfire_grace_time=3600,  # 서버 다운 등으로 놓쳐도 1시간 내 실행
    )
    _scheduler.start()
    logger.info(
        "crawl scheduler started: day=%s %02d:%02d KST",
        settings.crawl_schedule_day,
        settings.crawl_schedule_hour,
        settings.crawl_schedule_minute,
    )
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("crawl scheduler stopped")
