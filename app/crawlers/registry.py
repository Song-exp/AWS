"""크롤러 레지스트리 및 실행 오케스트레이션(월간 파이프라인).

월간 흐름: expire_past_postings(만료 처리) -> 대상 월 계산(당월+익월)
-> 각 어댑터 preflight -> fetch -> 마감일 정규화 -> 대상월 필터
-> content_key 기준 멱등 upsert -> CrawlRun 이력 기록.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crawlers.base import BaseCrawler, ComplianceError, RawPosting
from app.crawlers.date_parser import (
    is_within_months,
    normalize_deadline,
    target_year_months,
)
from app.crawlers.private import CampuspickCrawler, DreamsponCrawler
from app.crawlers.public import (
    KhuScholarshipCrawler,
    KosafCrawler,
    OnjungchoungnyeonCrawler,
)
from app.models.crawl_run import CrawlRun, CrawlRunStatus
from app.models.scholarship import PostingStatus, Scholarship

logger = logging.getLogger(__name__)

# 마감일을 목록에 노출하지 않는 게시판(대학 장학공지 등) 대응:
# 등록일이 이 기간 안이면 '모집중'으로 간주해 수집한다.
RECENT_POSTED_DAYS = 45

# 등록된 모든 어댑터
REGISTRY: list[type[BaseCrawler]] = [
    OnjungchoungnyeonCrawler,
    KosafCrawler,
    KhuScholarshipCrawler,
    DreamsponCrawler,
    CampuspickCrawler,
]


def _enrich_from_body(raw: RawPosting) -> None:
    """첨부에서 추출한 본문이 충분하면 구조화 정보를 병합한다.

    본문에서 마감일·자격·지급액·신청문항을 뽑아 RawPosting의 정형 필드를
    보강한다. 신청문항(application_questions)은 초안 생성 시 '공고 양식'으로
    쓰이므로 eligibility에 함께 보관한다.
    """
    body = raw.body_text or ""
    if len(body) < 200:  # 목록 요약(짧은 텍스트)은 제외, 첨부 본문만 처리
        return
    from app.services.posting_extract import extract_structured

    data = extract_structured(body)
    if not data:
        return

    if data.get("deadline_at"):
        raw.deadline_at = data["deadline_at"]

    elig = dict(raw.eligibility or {})
    elig.update({k: v for k, v in (data.get("eligibility") or {}).items() if v})
    if data.get("application_questions"):
        elig["application_questions"] = data["application_questions"]
    raw.eligibility = elig

    if data.get("benefit"):
        raw.benefit = {**(raw.benefit or {}), **data["benefit"]}
    if data.get("required_documents"):
        raw.required_documents = data["required_documents"]


def _to_model(raw: RawPosting) -> Scholarship:
    return Scholarship(
        content_key=raw.content_key(),
        title=raw.title,
        organization=raw.organization,
        source_type=raw.source_type,
        category=raw.category,
        source_platform=raw.source_platform,
        source_url=raw.source_url,
        deadline_at=raw.deadline_at,
        posted_at=raw.posted_at,
        eligibility=raw.eligibility,
        benefit=raw.benefit,
        required_documents=raw.required_documents,
        body_text=raw.body_text,
        content_hash=raw.content_hash(),
        status=PostingStatus.OPEN,
    )


def upsert_posting(db: Session, raw: RawPosting) -> bool:
    """content_key 기준 멱등 upsert. 신규 저장 시 True."""
    existing = db.scalar(
        select(Scholarship).where(Scholarship.content_key == raw.content_key())
    )
    if existing is None:
        db.add(_to_model(raw))
        return True
    # 변경 감지: 해시가 다르면 갱신(마감일 변경 시 상태도 재오픈)
    if existing.content_hash != raw.content_hash():
        existing.title = raw.title
        existing.deadline_at = raw.deadline_at
        existing.body_text = raw.body_text
        existing.eligibility = raw.eligibility
        existing.benefit = raw.benefit
        existing.required_documents = raw.required_documents
        existing.content_hash = raw.content_hash()
        if existing.status == PostingStatus.CLOSED and raw.deadline_at:
            # 마감일이 미래로 갱신되면 다시 열림
            now = datetime.now(timezone.utc)
            if raw.deadline_at > now:
                existing.status = PostingStatus.OPEN
    return False


def expire_past_postings(db: Session) -> int:
    """마감일이 지난 공고를 closed로 전환. 전환 건수 반환."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(Scholarship)
        .where(
            Scholarship.deadline_at.is_not(None),
            Scholarship.deadline_at < now,
            Scholarship.status.in_([PostingStatus.OPEN, PostingStatus.CLOSING_SOON]),
        )
        .values(status=PostingStatus.CLOSED)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0


def run_crawler(
    crawler: BaseCrawler,
    db: Session,
    target_months: set[tuple[int, int]],
) -> dict:
    """단일 어댑터 실행. 준수 체크 실패는 스킵으로 처리하고 리포트."""
    report = {"platform": crawler.platform, "fetched": 0, "saved": 0, "skipped": False}
    try:
        crawler.preflight(respect_robots=settings.crawl_respect_robots)
    except ComplianceError as e:
        logger.warning("compliance skip: %s", e)
        report["skipped"] = True
        report["reason"] = str(e)
        return report

    postings = crawler.fetch()
    report["fetched"] = len(postings)

    now = datetime.now(timezone.utc)
    for raw in postings:
        if raw.deadline_at is None and raw.deadline_raw:
            raw.deadline_at = normalize_deadline(raw.deadline_raw)

        # 첨부 본문이 충분하면 구조화 추출로 마감/자격/지급액/문항을 채운다.
        _enrich_from_body(raw)

        if raw.deadline_at is not None:
            # 마감일이 있으면 대상 월(당월+익월)로 필터
            if not is_within_months(raw.deadline_at, target_months):
                continue
        else:
            # 마감일 미공개 게시판: 최근 등록된 공고만 모집중으로 간주
            posted = raw.posted_at
            if posted is None:
                continue
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            if (now - posted).days > RECENT_POSTED_DAYS:
                continue

        if upsert_posting(db, raw):
            report["saved"] += 1

    db.commit()
    return report


def _resolve_target_months(
    target_months: set[tuple[int, int]] | None,
) -> set[tuple[int, int]]:
    if target_months:
        return target_months
    return target_year_months(months_ahead=settings.crawl_months_ahead)


def run_all(
    db: Session, target_months: set[tuple[int, int]] | None = None
) -> list[dict]:
    """레지스트리의 모든 어댑터를 대상 월 기준으로 실행."""
    months = _resolve_target_months(target_months)
    return [run_crawler(cls(), db, months) for cls in REGISTRY]


def run_monthly_update(
    db: Session,
    trigger: str = "scheduled",
    target_months: set[tuple[int, int]] | None = None,
) -> CrawlRun:
    """월간 갱신 진입점: 만료 처리 -> 대상월 크롤 -> CrawlRun 이력 기록."""
    months = _resolve_target_months(target_months)
    run = CrawlRun(
        trigger=trigger,
        target_months=sorted([list(m) for m in months]),
        status=CrawlRunStatus.RUNNING,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        expired = expire_past_postings(db)
        reports = [run_crawler(cls(), db, months) for cls in REGISTRY]

        run.total_expired = expired
        run.total_fetched = sum(r.get("fetched", 0) for r in reports)
        run.total_saved = sum(r.get("saved", 0) for r in reports)
        run.per_platform = reports
        run.finished_at = datetime.now(timezone.utc)
        run.status = (
            CrawlRunStatus.PARTIAL
            if any(r.get("skipped") for r in reports)
            else CrawlRunStatus.SUCCESS
        )
    except Exception as e:  # noqa: BLE001 - 실행 이력에 실패를 기록해야 함
        logger.exception("monthly crawl failed")
        run.status = CrawlRunStatus.FAILED
        run.error = str(e)
        run.finished_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(run)
    return run
