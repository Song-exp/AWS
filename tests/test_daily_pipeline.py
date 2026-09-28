"""일간 파이프라인: 게시판은 새 글만 상세 수집, API는 모집중 목록과 동기화."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.crawlers.base import BaseCrawler, RawPosting
from app.crawlers.registry import run_crawler
from app.models.crawl_run import CrawlRun, CrawlRunStatus
from app.models.scholarship import Category, Scholarship, SourceType
from tests.conftest import KST, make_scholarship


class FakeCrawler(BaseCrawler):
    tos_allows_crawling = True

    def __init__(self, platform, posts, full_sync=False):
        self.platform, self.posts, self.full_sync = platform, posts, full_sync
        self.detailed = []

    def fetch(self):
        return list(self.posts)

    def fetch_detail(self, raw):
        self.detailed.append(raw.title)


def _raw(title, platform, deadline=None, posted=None):
    return RawPosting(
        title=title, source_url=f"https://x.test/{title}", source_platform=platform,
        source_type=SourceType.PUBLIC, category=Category.SCHOLARSHIP,
        deadline_at=deadline, posted_at=posted,
    )


def _titles(db, platform):
    return set(db.scalars(select(Scholarship.title).where(Scholarship.source_platform == platform)))


def test_board_adds_open_new_posts_then_skips_processed_ones(db):
    now = datetime.now(KST)
    posts = [
        _raw("모집중", "board", deadline=now + timedelta(days=5), posted=now),
        _raw("이미마감", "board", deadline=now - timedelta(days=1), posted=now),
        _raw("날짜없음-최근", "board", posted=now - timedelta(days=3)),
        _raw("날짜없음-오래됨", "board", posted=now - timedelta(days=60)),
    ]
    first = FakeCrawler("board", posts)
    assert run_crawler(first, db)["saved"] == 2
    assert len(first.detailed) == 4
    assert _titles(db, "board") == {"모집중", "날짜없음-최근"}

    utc_now = datetime.now(timezone.utc)
    db.add(CrawlRun(
        trigger="scheduled", status=CrawlRunStatus.SUCCESS, started_at=utc_now,
        finished_at=utc_now, per_platform=[{"platform": "board", "skipped": False}],
    ))
    db.commit()

    yesterday = _raw("어제글", "board", deadline=now + timedelta(days=5), posted=now - timedelta(days=1))
    second = FakeCrawler("board", posts + [yesterday])
    run_crawler(second, db)
    # 저장된 글과 직전 실행 날짜 이전 글은 상세·LLM을 다시 부르지 않는다.
    # 같은 날짜에 올라왔지만 저장되지 않은 글(이미마감)만 한 번 더 본다.
    assert second.detailed == ["이미마감"]


def test_board_removes_undated_posts_past_ttl(db):
    now = datetime.now(KST)
    db.add(make_scholarship(title="오래된공지", source_platform="board", deadline_at=None,
                            posted_at=now - timedelta(days=60)))
    db.add(make_scholarship(title="최근공지", source_platform="board", deadline_at=None,
                            posted_at=now - timedelta(days=3)))
    db.commit()

    assert run_crawler(FakeCrawler("board", []), db)["removed"] == 1
    assert _titles(db, "board") == {"최근공지"}


def test_full_sync_removes_postings_missing_from_source(db):
    db.add(make_scholarship(title="내려간정책", source_platform="api"))
    db.add(make_scholarship(title="다른소스", source_platform="board"))
    db.commit()

    kept = _raw("유지정책", "api", deadline=datetime.now(KST) + timedelta(days=5))
    crawler = FakeCrawler("api", [kept], full_sync=True)
    report = run_crawler(crawler, db)

    assert report["removed"] == 1 and crawler.detailed == []
    assert _titles(db, "api") == {"유지정책"}
    assert _titles(db, "board") == {"다른소스"}
