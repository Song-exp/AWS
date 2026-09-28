"""크롤러 공통 기반: 어댑터 인터페이스, DTO, 준수(compliance) 체크."""
from __future__ import annotations

import abc
import hashlib
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

from app.models.scholarship import Category, SourceType


@dataclass
class RawPosting:
    """어댑터가 반환하는 표준 공고 DTO. 모델(Scholarship)로 매핑된다."""

    title: str
    source_url: str
    source_platform: str
    source_type: SourceType
    category: Category
    organization: str | None = None
    deadline_raw: str | None = None          # 정규화 전 원문 마감 표기
    deadline_at: datetime | None = None       # 정규화 결과
    posted_at: datetime | None = None         # 게시판 등록일(마감일 미공개 사이트 대응)
    eligibility: dict = field(default_factory=dict)
    benefit: dict = field(default_factory=dict)
    required_documents: list[str] = field(default_factory=list)
    body_text: str = ""

    def content_key(self) -> str:
        """멱등성 키: 플랫폼 + URL 해시."""
        raw = f"{self.source_platform}::{self.source_url}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]

    def content_hash(self) -> str:
        """변경 감지용 본문 해시."""
        raw = f"{self.title}|{self.deadline_raw}|{self.body_text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


class ComplianceError(Exception):
    """robots.txt 또는 ToS 위반 시."""


def check_robots(url: str, user_agent: str = "*") -> bool:
    """robots.txt 상 크롤링 허용 여부. 확인 실패 시 보수적으로 True(차단 아님)로 두되,
    호출부에서 CRAWL_RESPECT_ROBOTS 설정과 함께 판단한다."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception:
        # robots를 읽지 못하면 판단 보류(상위에서 결정)
        return True
    return rp.can_fetch(user_agent, url)


class BaseCrawler(abc.ABC):
    """모든 소스 어댑터의 공통 인터페이스.

    민간 플랫폼은 ToS 준수가 특히 중요하므로, 각 어댑터가
    `tos_allows_crawling`을 명시적으로 선언하도록 강제한다.
    """

    #: 소스 식별자 (예: 'khu_janghak', 'onjungchoungnyeon')
    platform: str = "base"
    #: True(API): fetch()가 모집중 전체를 돌려준다. 매 실행 동기화하고 빠진 공고는 삭제.
    #: False(게시판): 새 글만 fetch_detail()로 상세를 받아 본문에서 구조화한다.
    full_sync: bool = False
    #: 공공/민간
    source_type: SourceType = SourceType.PUBLIC
    #: 장학금/정부혜택
    category: Category = Category.SCHOLARSHIP
    #: ToS 상 크롤링 허용 여부 (Day 0 실사 결과를 여기 반영)
    tos_allows_crawling: bool = False
    #: 대상 베이스 URL
    base_url: str = ""

    def preflight(self, respect_robots: bool = True) -> None:
        """수집 전 준수 체크. 위반 시 ComplianceError."""
        if not self.tos_allows_crawling:
            raise ComplianceError(
                f"[{self.platform}] ToS 크롤링 허용이 확인되지 않음. Day 0 실사 후 활성화 필요."
            )
        if respect_robots and self.base_url and not check_robots(self.base_url):
            raise ComplianceError(f"[{self.platform}] robots.txt가 크롤링을 불허함: {self.base_url}")

    @abc.abstractmethod
    def fetch(self) -> list[RawPosting]:
        """공고 목록을 수집해 표준 DTO 리스트로 반환."""
        raise NotImplementedError

    def fetch_detail(self, raw: RawPosting) -> None:
        """게시판형 새 글의 상세 본문·첨부를 raw에 채운다. 기본은 할 일 없음."""
