"""민간 플랫폼(장학금) 어댑터.

민간 플랫폼은 ToS 상 크롤링을 금지하는 경우가 많다. 각 어댑터의
`tos_allows_crawling`은 기본 False이며, robots.txt 실사에서 허용이
확인된 사이트만 True로 전환한다. 원문 전체 저장보다 핵심 필드 + 원본
링크 유도를 우선해 저작권 리스크를 낮춘다.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta, timezone

from app.crawlers.base import BaseCrawler, RawPosting
from app.models.scholarship import Category, SourceType

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 'D-1 마감임박', 'D-32 모집중' = 모집중 / 'D+29 모집마감' = 이미 마감
_DDAY_RE = re.compile(r"D\s*-\s*(\d+)")
_DDAY_CLOSED_RE = re.compile(r"D\s*\+\s*(\d+)")
_DDAY_TODAY_RE = re.compile(r"D\s*-?\s*DAY", re.IGNORECASE)
# 제목 뒤에 붙는 해시태그 분리용
_HASHTAG_RE = re.compile(r"#\S+")


class DreamsponCrawler(BaseCrawler):
    """드림스폰 - 민간 장학금 모음.

    robots.txt 실사(2026-08): `Allow: /` 이며 /admin/, /manager/ 및 특정
    상세 1건만 Disallow. 목록 경로 /dreamscholarship/list.html 은 허용된다.

    목록 구조(확인됨):
        tr > td.td_subject(제목+태그) / td(주관기관) / td.td_day(D-n) / td.td_hit(조회수)
    마감일은 D-day를 기준으로 계산한다(사이트가 절대 날짜를 목록에 노출하지 않음).
    """

    platform = "dreamspon"
    source_type = SourceType.PRIVATE
    category = Category.SCHOLARSHIP
    base_url = "https://www.dreamspon.com"
    tos_allows_crawling = True  # robots.txt Allow 확인(2026-08 실사)

    list_path = "/dreamscholarship/list.html"
    #: 목록 페이지네이션(?page=N). 모집중 공고를 충분히 확보하려면 여러 장 필요.
    max_pages = 4
    user_agent = "ScholarshipMVP/0.1 (+research; respects robots)"

    #: 장학금이 아닌 제휴 광고성 항목을 제외하기 위한 키워드
    _EXCLUDE_KEYWORDS = ("치과", "안과", "라식", "라섹", "교정", "인터뷰", "이벤트 후기")

    def _deadline_from_dday(self, text: str, today: date | None = None) -> datetime | None:
        """'D-4' 같은 표기를 실제 마감일시로 변환.

        'D+n 모집마감'은 이미 마감된 공고이므로 None을 반환해 상위에서
        제외되게 한다(모집중 공고만 사용자에게 노출).
        """
        base = today or datetime.now(KST).date()
        if _DDAY_CLOSED_RE.search(text):
            return None  # 이미 마감
        if _DDAY_TODAY_RE.search(text):
            return datetime.combine(base, time(23, 59), tzinfo=KST)
        m = _DDAY_RE.search(text)
        if not m:
            return None
        days = int(m.group(1))
        return datetime.combine(base + timedelta(days=days), time(23, 59), tzinfo=KST)

    def fetch(self) -> list[RawPosting]:
        import time as _time

        import httpx
        from bs4 import BeautifulSoup

        from app.core.config import settings

        results: list[RawPosting] = []
        headers = {"User-Agent": self.user_agent}
        seen: set[str] = set()

        with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
            for page in range(1, self.max_pages + 1):
                url = f"{self.base_url}{self.list_path}"
                if page > 1:
                    url += f"?page={page}"
                resp = client.get(url)
                if resp.status_code != 200:
                    logger.warning("dreamspon list fetch failed: %s", resp.status_code)
                    break

                soup = BeautifulSoup(resp.text, "lxml")
                new_on_page = 0

                for a in soup.select('a[href*="view.html?idx="]'):
                    tr = a.find_parent("tr")
                    if tr is None:
                        continue
                    tds = tr.find_all("td")
                    if len(tds) < 3:
                        continue

                    href = a.get("href") or ""
                    if href in seen:
                        continue
                    seen.add(href)
                    new_on_page += 1

                    subject_raw = " ".join(tds[0].get_text(" ", strip=True).split())
                    title = _HASHTAG_RE.sub("", subject_raw).strip()
                    tags = _HASHTAG_RE.findall(subject_raw)
                    organization = " ".join(tds[1].get_text(" ", strip=True).split())
                    dday_text = " ".join(tds[2].get_text(" ", strip=True).split())

                    if not title:
                        continue
                    # 장학금과 무관한 제휴 광고/인터뷰성 게시물 제외
                    if any(k in title for k in self._EXCLUDE_KEYWORDS):
                        continue

                    deadline = self._deadline_from_dday(dday_text)
                    if deadline is None:
                        continue  # 이미 마감되었거나 마감일 불명 → 노출하지 않음

                    detail_url = f"{self.base_url}{href}" if href.startswith("/") else href

                    results.append(
                        RawPosting(
                            title=title,
                            source_url=detail_url,
                            source_platform=self.platform,
                            source_type=self.source_type,
                            category=self.category,
                            organization=organization or None,
                            deadline_raw=dday_text,
                            deadline_at=deadline,
                            # 저작권 고려: 원문 전문 대신 제목/태그 요약만 보관하고 링크로 유도
                            body_text=f"{title}\n태그: {' '.join(tags)}\n주관: {organization}",
                            eligibility={},
                            benefit={},
                        )
                    )

                if new_on_page == 0:
                    break  # 더 이상 새 항목이 없으면 중단
                _time.sleep(settings.crawl_default_delay_sec)  # rate limit 준수

        return results


class CampuspickCrawler(BaseCrawler):
    """캠퍼스픽 - 장학/대외활동.

    robots.txt에 다수 Disallow 경로가 있어 실사 후 개별 확인이 필요하다.
    """

    platform = "campuspick"
    source_type = SourceType.PRIVATE
    category = Category.SCHOLARSHIP
    base_url = "https://www.campuspick.com"
    tos_allows_crawling = False  # 개별 경로 실사 후 전환

    def fetch(self) -> list[RawPosting]:
        return []
