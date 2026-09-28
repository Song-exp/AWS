"""일간 파이프라인 스케줄러(APScheduler).

매일 00:10 KST(날짜가 바뀐 직후)에 run_daily_update를 실행한다:
마감 공고 삭제 -> 신규 공고 수집·추가. FastAPI lifespan에서 start/shutdown 한다.
설정으로 on/off.
"""
from __future__ import annotations

import logging
from datetime import timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.db import SessionLocal
from app.crawlers.registry import run_daily_update
from app.services.reminders import send_deadline_reminders

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_JOB_ID = "daily_crawl_update"
_REMINDER_JOB_ID = "daily_deadline_reminder"

_scheduler: BackgroundScheduler | None = None


def _scheduled_job() -> None:
    """스케줄러가 호출하는 작업. 자체 DB 세션을 열고 닫는다."""
    db = SessionLocal()
    try:
        run = run_daily_update(db, trigger="scheduled")
        logger.info(
            "daily crawl done: run_id=%s status=%s saved=%s removed=%s",
            run.id, run.status, run.total_saved, run.total_expired,
        )
        # 만료·폐기된 세션 정리. 검증이 만료를 확인하므로 기능상 필수는
        # 아니지만, 두면 auth_sessions 가 무한정 자란다.
        from app.core.security import purge_expired_sessions

        purged = purge_expired_sessions(db)
        logger.info("expired sessions purged: %s", purged)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled daily crawl failed")
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
    if settings.deadline_reminder_enabled:
        _scheduler.add_job(
            _reminder_job,
            trigger=CronTrigger(
                hour=settings.deadline_reminder_hour, minute=0, timezone=KST
            ),
            id=_REMINDER_JOB_ID,
            replace_existing=True,
            misfire_grace_time=3600,
        )

    _scheduler.start()
    logger.info(
        "crawl scheduler started: daily %02d:%02d KST",
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


def _reminder_job() -> None:
    """마감 임박 공고를 메일로 알린다(매일 09:00 KST).

    부품이 이미 다 있어서 잇기만 하면 되는 작업이다 —
    deadline_at(공고) + smtplib(mailer) + APScheduler(여기).
    """
    db = SessionLocal()
    try:
        sent = send_deadline_reminders(db)
        logger.info("deadline reminders sent: %s", sent)
    except Exception:  # noqa: BLE001
        logger.exception("deadline reminder job failed")
    finally:
        db.close()
