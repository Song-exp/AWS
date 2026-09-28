"""크롤러 레지스트리 및 일간 파이프라인.

매일(기본 00:10 KST, 날짜가 바뀐 직후):
  purge_expired_postings(마감 공고 삭제) -> 소스별 수집·신규 추가 -> CrawlRun 기록

소스 유형(BaseCrawler.full_sync):
  - API(True): 모집중 전체를 받아 upsert하고, 목록에서 빠진 공고는 삭제한다.
  - 게시판(False): 직전 성공 실행 이후 올라온 새 글만 상세·첨부를 받아 구조화한다.
    매일 같은 글을 다시 내려받거나 LLM을 다시 부르지 않기 위해서다. 마감일을
    못 뽑은 글은 등록 후 UNDATED_TTL_DAYS 동안만 모집중으로 둔다.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crawlers.base import BaseCrawler, ComplianceError, RawPosting
from app.crawlers.date_parser import KST, normalize_deadline
from app.crawlers.public import KhuScholarshipCrawler, OnjungchoungnyeonCrawler
from app.models.application import UserApplication
from app.models.crawl_run import CrawlRun, CrawlRunStatus
from app.models.scholarship import PostingStatus, Scholarship, ScholarshipEmbedding

logger = logging.getLogger(__name__)

#: 마감일을 알 수 없는 게시판 글(대학 장학공지 등)을 모집중으로 볼 기간(등록일 기준).
UNDATED_TTL_DAYS = 45

# 등록된 모든 어댑터
REGISTRY: list[type[BaseCrawler]] = [
    OnjungchoungnyeonCrawler,
    KhuScholarshipCrawler,
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
    # 변경 감지: 해시가 다르면 갱신
    if existing.content_hash != raw.content_hash():
        existing.title = raw.title
        existing.deadline_at = raw.deadline_at
        existing.body_text = raw.body_text
        existing.eligibility = raw.eligibility
        existing.benefit = raw.benefit
        existing.required_documents = raw.required_documents
        existing.content_hash = raw.content_hash()
    return False


def _delete_postings(db: Session, ids) -> int:
    """id 서브쿼리에 해당하는 공고 삭제. 삭제 건수 반환(commit은 호출부).

    신청 이력은 공고명을 스냅샷해 두므로 연결만 끊는다.
    SQLite는 FK 연쇄(ondelete)가 꺼져 있어 참조 정리를 직접 한다.
    """
    db.execute(
        update(UserApplication)
        .where(UserApplication.scholarship_id.in_(ids))
        .values(scholarship_id=None)
    )
    db.execute(delete(ScholarshipEmbedding).where(ScholarshipEmbedding.scholarship_id.in_(ids)))
    return db.execute(delete(Scholarship).where(Scholarship.id.in_(ids))).rowcount or 0


def purge_expired_postings(db: Session) -> int:
    """마감일이 지난 공고를 삭제. 삭제 건수 반환."""
    # SQLite는 tz를 버리고 KST 벽시계 시각으로 저장하므로 KST로 비교한다(PG도 동일 결과).
    removed = _delete_postings(
        db,
        select(Scholarship.id).where(
            Scholarship.deadline_at.is_not(None),
            Scholarship.deadline_at < datetime.now(KST),
        ),
    )
    db.commit()
    return removed


def _last_success_date(db: Session, platform: str) -> date | None:
    """이 소스를 마지막으로 정상 수집한 실행의 날짜(KST). 없으면 None."""
    runs = db.scalars(
        select(CrawlRun)
        .where(CrawlRun.finished_at.is_not(None))
        .order_by(CrawlRun.id.desc())
        .limit(60)
    )
    for run in runs:
        reports = run.per_platform or []
        if any(r.get("platform") == platform and not r.get("skipped") for r in reports):
            started = run.started_at
            if started.tzinfo is None:  # SQLite는 CURRENT_TIMESTAMP(UTC)를 naive로 돌려준다
                started = started.replace(tzinfo=timezone.utc)
            return started.astimezone(KST).date()
    return None


def run_crawler(crawler: BaseCrawler, db: Session) -> dict:
    """단일 어댑터 실행. 준수 체크·수집 실패는 스킵으로 리포트."""
    report = {
        "platform": crawler.platform, "fetched": 0, "saved": 0, "removed": 0, "skipped": False,
    }
    try:
        crawler.preflight(respect_robots=settings.crawl_respect_robots)
    except ComplianceError as e:
        logger.warning("compliance skip: %s", e)
        report["skipped"] = True
        report["reason"] = str(e)
        return report

    since = None if crawler.full_sync else _last_success_date(db, crawler.platform)
    try:
        postings = crawler.fetch()
    except Exception as e:  # noqa: BLE001 - 한 소스 장애가 다른 소스 수집을 막지 않게
        logger.exception("fetch failed: %s", crawler.platform)
        report["skipped"] = True
        # 예외 메시지에는 요청 URL(API 키 포함)이 섞일 수 있어 타입만 남긴다.
        report["reason"] = f"fetch 실패: {type(e).__name__}"
        return report
    report["fetched"] = len(postings)

    now = datetime.now(timezone.utc)
    undated_cutoff = now - timedelta(days=UNDATED_TTL_DAYS)
    open_keys: set[str] = set()
    for raw in postings:
        if not crawler.full_sync:
            # 직전 성공 실행 전에 올라온 글, 이미 저장된 글은 처리가 끝난 글이다.
            if since and raw.posted_at and raw.posted_at.date() < since:
                continue
            if db.scalar(select(Scholarship.id).where(Scholarship.content_key == raw.content_key())):
                continue
            # 새 글만 상세·첨부를 받고 본문에서 마감일·자격·지급액을 구조화한다.
            crawler.fetch_detail(raw)
            _enrich_from_body(raw)

        if raw.deadline_at is None and raw.deadline_raw:
            raw.deadline_at = normalize_deadline(raw.deadline_raw)

        if raw.deadline_at is not None:
            if raw.deadline_at < now:
                continue  # 이미 마감
        elif not crawler.full_sync:
            # 마감일 미공개 게시판 글: 최근 등록된 것만 모집중으로 간주
            posted = raw.posted_at
            if posted is None:
                continue
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            if posted < undated_cutoff:
                continue

        open_keys.add(raw.content_key())
        if upsert_posting(db, raw):
            report["saved"] += 1

    stale = None
    if crawler.full_sync:
        # 오늘 모집중 목록에 없는 공고는 마감됐거나 내려간 것이다.
        if open_keys:
            stale = select(Scholarship.id).where(
                Scholarship.source_platform == crawler.platform,
                Scholarship.content_key.not_in(open_keys),
            )
    else:
        stale = select(Scholarship.id).where(
            Scholarship.source_platform == crawler.platform,
            Scholarship.deadline_at.is_(None),
            Scholarship.posted_at < datetime.now(KST) - timedelta(days=UNDATED_TTL_DAYS),
        )
    if stale is not None:
        report["removed"] = _delete_postings(db, stale)

    db.commit()
    return report


def run_daily_update(db: Session, trigger: str = "scheduled") -> CrawlRun:
    """일간 갱신 진입점: 마감 삭제 -> 소스별 수집·추가 -> CrawlRun 이력 기록."""
    # 크롤 도중 프로세스가 죽으면 기록이 RUNNING 으로 영원히 남는다. 정상 실행은
    # 몇 분이면 끝나므로 1시간 넘게 RUNNING 인 것은 죽은 실행으로 본다.
    db.execute(
        update(CrawlRun)
        .where(
            CrawlRun.status == CrawlRunStatus.RUNNING,
            CrawlRun.started_at < datetime.now(timezone.utc) - timedelta(hours=1),
        )
        .values(
            status=CrawlRunStatus.FAILED,
            error="실행 도중 중단됨(프로세스 종료)",
            finished_at=datetime.now(timezone.utc),
        )
    )
    run = CrawlRun(trigger=trigger, status=CrawlRunStatus.RUNNING)
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        expired = purge_expired_postings(db)
        reports = [run_crawler(cls(), db) for cls in REGISTRY]

        run.total_expired = expired + sum(r["removed"] for r in reports)
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
        logger.exception("daily crawl failed")
        db.rollback()
        run.status = CrawlRunStatus.FAILED
        run.error = str(e)
        run.finished_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(run)
    return run
