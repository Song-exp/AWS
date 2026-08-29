"""공공기관(정부 혜택) 어댑터.

MVP에서는 인터페이스와 수집 흐름만 스캐폴딩한다. 실제 셀렉터/엔드포인트는
Day 0 소스 실사 후 채운다. 공공데이터는 대체로 재사용 우호적이지만,
각 포털의 이용약관을 개별 확인한다.
"""
from __future__ import annotations

import logging
import re

from app.crawlers.base import BaseCrawler, RawPosting
from app.models.scholarship import Category, SourceType

logger = logging.getLogger(__name__)


class OnjungchoungnyeonCrawler(BaseCrawler):
    """온통청년(청년포털) - 청년정책/지원금."""

    platform = "onjungchoungnyeon"
    source_type = SourceType.PUBLIC
    category = Category.GOV_BENEFIT
    base_url = "https://www.youthcenter.go.kr"
    tos_allows_crawling = False  # Day 0 실사 후 True로 전환

    def fetch(self) -> list[RawPosting]:
        # TODO(Day1-3): 공공데이터 Open API 우선 탐색, 없으면 목록 파싱.
        # 반환 예시 형태만 문서화하고 실제 수집은 미구현.
        return []


class KhuScholarshipCrawler(BaseCrawler):
    """경희대학교 장학공지 게시판.

    robots.txt 실사(2026-08): `Disallow: /cms/`, `/upload/` 뿐이라 게시판
    경로(/janghak/user/bbs/)는 허용된다.

    목록 구조(확인됨):
        tr > td(구분) / td(카테고리: 공통_교외장학|공통_교내장학) / td(제목)
             / td(첨부) / td(등록일 YYYY-MM-DD)
        상세는 view.do?menuNo=..&boardId=.. (GET 가능)

    주의: 이 게시판은 **목록에 마감일이 없다**(본문이 HWPX 첨부에 있음).
    그래서 deadline_at은 제목에서 찾을 수 있을 때만 채우고, 대신
    posted_at(등록일)을 기록해 상위 파이프라인이 '최근 등록=모집중'으로
    판단하게 한다.
    """

    platform = "khu_janghak"
    source_type = SourceType.PUBLIC
    category = Category.SCHOLARSHIP
    base_url = "https://janghak.khu.ac.kr"
    tos_allows_crawling = True  # robots.txt 실사 완료(2026-08)

    bbs_path = "/janghak/user/bbs/BMSR00040"
    menu_no = "12300032"
    max_pages = 3
    user_agent = "ScholarshipMVP/0.1 (+research; respects robots)"
    #: 첨부(HWPX/PDF)를 열어 본문까지 수집할 상위 건수. 요청 수를 제한한다.
    enrich_detail_count = 12

    def _fetch_attachment_text(self, client, detail_url: str) -> tuple[str, str | None]:
        """상세 페이지의 첫 첨부를 내려받아 텍스트를 추출. (본문, 첨부파일명)."""
        from bs4 import BeautifulSoup

        from app.utils.file_parser import UnsupportedFileType, extract_text_from_bytes

        try:
            r = client.get(detail_url)
            if r.status_code != 200 or "에러안내" in r.text:
                return "", None
            soup = BeautifulSoup(r.text, "lxml")
            # 텍스트 추출 가능한 첨부(hwpx/hwp/pdf/docx)를 우선 선택
            chosen_href, chosen_name = None, None
            for a in soup.select('a[href*="fileDown"]'):
                nm = " ".join(a.get_text(" ", strip=True).split())
                if nm.lower().endswith((".hwpx", ".hwp", ".pdf", ".docx", ".txt")):
                    chosen_href, chosen_name = a.get("href") or "", nm
                    break
            if chosen_href is None:
                return "", None
            dl = chosen_href if chosen_href.startswith("http") else f"{self.base_url}{chosen_href}"
            fr = client.get(dl)
            if fr.status_code != 200 or not fr.content:
                return "", chosen_name
            try:
                text = extract_text_from_bytes(fr.content, chosen_name)
            except UnsupportedFileType:
                return "", chosen_name
            return text, chosen_name
        except Exception:  # noqa: BLE001 - 첨부 실패가 목록 수집을 막지 않게
            logger.warning("khu attachment fetch failed: %s", detail_url)
            return "", None

    def fetch(self) -> list[RawPosting]:
        import time as _time
        from datetime import datetime, time as dtime, timedelta, timezone

        import httpx
        from bs4 import BeautifulSoup

        from app.core.config import settings
        from app.crawlers.date_parser import normalize_deadline

        KST = timezone(timedelta(hours=9))
        results: list[RawPosting] = []
        headers = {"User-Agent": self.user_agent}
        seen: set[str] = set()

        with httpx.Client(timeout=25, follow_redirects=True, headers=headers) as client:
            for page in range(1, self.max_pages + 1):
                resp = client.get(
                    f"{self.base_url}{self.bbs_path}/list.do",
                    params={"menuNo": self.menu_no, "pageIndex": page},
                )
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, "lxml")
                table = soup.find("table")
                if table is None:
                    break

                new_on_page = 0
                for tr in table.select("tbody tr"):
                    tds = tr.find_all("td")
                    a = tr.select_one("a")
                    if a is None or len(tds) < 5:
                        continue

                    # href='javascript:view('551046');' 에서 boardId 추출
                    href = a.get("href") or ""
                    m = re.search(r"view\('(\d+)'\)", href)
                    if not m:
                        continue
                    board_id = m.group(1)
                    if board_id in seen:
                        continue
                    seen.add(board_id)
                    new_on_page += 1

                    category_text = " ".join(tds[1].get_text(" ", strip=True).split())
                    title = " ".join(tds[2].get_text(" ", strip=True).split())
                    posted_text = " ".join(tds[4].get_text(" ", strip=True).split())

                    if not title:
                        continue

                    posted_at = None
                    pm = re.search(r"(20\d{2})-(\d{2})-(\d{2})", posted_text)
                    if pm:
                        posted_at = datetime(
                            int(pm.group(1)), int(pm.group(2)), int(pm.group(3)),
                            tzinfo=KST,
                        )

                    # 제목에 마감 표기가 있으면 사용(없으면 None → posted_at으로 판단)
                    deadline_at = normalize_deadline(title)

                    detail_url = (
                        f"{self.base_url}{self.bbs_path}/view.do"
                        f"?menuNo={self.menu_no}&boardId={board_id}"
                    )

                    scope = "교외" if "교외" in category_text else (
                        "교내" if "교내" in category_text else "기타"
                    )

                    results.append(
                        RawPosting(
                            title=title,
                            source_url=detail_url,
                            source_platform=self.platform,
                            source_type=self.source_type,
                            category=self.category,
                            organization="경희대학교 장학팀",
                            deadline_raw=None,
                            deadline_at=deadline_at,
                            posted_at=posted_at,
                            body_text=f"{title}\n구분: {category_text}\n등록일: {posted_text}",
                            eligibility={"scope": scope, "school": "경희대학교"},
                            benefit={},
                        )
                    )

                if new_on_page == 0:
                    break
                _time.sleep(settings.crawl_default_delay_sec)

            # 상위 N건은 첨부(HWPX/PDF)를 열어 본문까지 채운다.
            # 본문이 있으면 마감일·자격·지급액 구조화 추출의 소스가 된다.
            for raw in results[: self.enrich_detail_count]:
                body, fname = self._fetch_attachment_text(client, raw.source_url)
                if body:
                    raw.body_text = body
                    if fname:
                        raw.required_documents = [fname]
                _time.sleep(settings.crawl_default_delay_sec)

        return results


class KosafCrawler(BaseCrawler):
    """한국장학재단 - 재단뉴스/공지 게시판.

    robots.txt 실사 결과 `User-agent: * Allow: /`로 크롤링이 허용됨.
    게시판은 정적(SSR) HTML이라 httpx + BeautifulSoup로 파싱한다.
    상세 마감일/자격이 정형 필드로 제공되지 않으므로, 목록의 제목·등록일·
    상세링크·본문을 수집한다(파이프라인 실데이터 확보 목적).
    """

    platform = "kosaf"
    source_type = SourceType.PUBLIC
    category = Category.GOV_BENEFIT
    base_url = "https://www.kosaf.go.kr"
    tos_allows_crawling = True  # robots.txt Allow: / 확인 (2026-08 실사)

    #: 수집 대상 게시판 경로(재단뉴스). 공지사항은 /ko/notice.do
    list_path = "/ko/news.do"
    #: 수집 페이지 수 (한 페이지 10건)
    max_pages = 1
    user_agent = "ScholarshipMVP/0.1 (+research; respects robots)"

    def fetch(self) -> list[RawPosting]:
        import time

        import httpx
        from bs4 import BeautifulSoup

        from app.core.config import settings
        from app.crawlers.date_parser import normalize_deadline

        results: list[RawPosting] = []
        headers = {"User-Agent": self.user_agent}

        with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
            for page in range(1, self.max_pages + 1):
                url = f"{self.base_url}{self.list_path}?page={page}"
                resp = client.get(url)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "lxml")
                table = soup.select_one("div.board_list table")
                if table is None:
                    break
                for tr in table.select("tbody tr"):
                    a = tr.select_one("a")
                    tds = tr.find_all("td")
                    if a is None or len(tds) < 3:
                        continue
                    title = a.get_text(strip=True)
                    href = a.get("href") or ""
                    detail_url = (
                        f"{self.base_url}{self.list_path}{href}"
                        if href.startswith("?")
                        else href
                    )
                    posted_at = tds[2].get_text(strip=True)  # 'YYYY.MM.DD' (등록일)

                    # 주의: 등록일은 마감일이 아니다. 제목에서 마감 표기를 찾고,
                    # 없으면 deadline_at을 비워 상위에서 needs_review로 격리한다.
                    deadline = normalize_deadline(title)

                    results.append(
                        RawPosting(
                            title=title,
                            source_url=detail_url,
                            source_platform=self.platform,
                            source_type=self.source_type,
                            category=self.category,
                            organization="한국장학재단",
                            deadline_raw=None,
                            deadline_at=deadline,
                            body_text=title,
                            eligibility={},
                            benefit={},
                        )
                    )
                    # 등록일은 참고용으로 본문에 남긴다
                    results[-1].body_text = f"{title}\n(등록일 {posted_at})"
                time.sleep(settings.crawl_default_delay_sec)  # rate limit 준수

        return results
