"""공공 소스 어댑터: 온통청년 청년정책 API, 경희대 장학공지 게시판."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.crawlers.base import BaseCrawler, ComplianceError, RawPosting
from app.models.scholarship import Category, SourceType

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 시군구 코드 앞 2자리 -> 시도. 특별자치도 전환 후 코드(강원 51, 전북 52)도 둔다.
_SIDO_BY_PREFIX = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주",
    "30": "대전", "31": "울산", "36": "세종", "41": "경기", "42": "강원",
    "43": "충북", "44": "충남", "45": "전북", "46": "전남", "47": "경북",
    "48": "경남", "50": "제주", "51": "강원", "52": "전북",
}
_ALL_SIDO = set(_SIDO_BY_PREFIX.values())
# 전남광주통합특별시 출범으로 광주·전남이 앞자리 12를 공유한다(API 실측).
# 프로필은 여전히 광주/전남으로 나뉘므로 광주 자치구 코드만 따로 가른다.
_GWANGJU_CODES = {"12210", "12240", "12270", "12300", "12330"}


def _sido(code: str) -> str | None:
    if code.startswith("12"):
        return "광주" if code in _GWANGJU_CODES else "전남"
    return _SIDO_BY_PREFIX.get(code[:2])


def _regions_from_zip(zip_cd: str) -> list[str]:
    """'41111,41113,...' -> ['경기']. 17개 시도를 다 덮으면 ['전국']."""
    regions = {s for z in (zip_cd or "").split(",") if (s := _sido(z.strip()))}
    if regions == _ALL_SIDO:
        return ["전국"]
    return sorted(regions)


def _parse_kst(text: str | None, fmt: str) -> datetime | None:
    try:
        return datetime.strptime((text or "").strip(), fmt).replace(tzinfo=KST)
    except ValueError:
        return None


class OnjungchoungnyeonCrawler(BaseCrawler):
    """온통청년 청년정책 Open API(getPlcy).

    신청기간구분(aplyPrdSeCd)별 처리(2026-09 전체 2,773건 실측):
      - 0057001 특정기간: 신청기간(aplyYmd 'YYYYMMDD ~ YYYYMMDD') 끝 날짜가 마감일
      - 0057002 상시: 신청기간이 비어 있다. 사업기간 종료일(bizPrdEndYmd)이 있으면
        그날을 마감일로, 없으면('연중', '사업비 소진 시 조기 마감') 마감일 없이 둔다
      - 0057003 마감: 신청기간이 비었고 제목에 '[9월 마감]', '[소진 마감]' 등이
        붙는다. 수집하지 않는다
    모집중 전체를 매번 받으므로(full_sync) 목록에서 빠진 정책은 상위에서 삭제된다.
    """

    platform = "onjungchoungnyeon"
    source_type = SourceType.PUBLIC
    category = Category.GOV_BENEFIT
    tos_allows_crawling = True  # 공식 Open API
    full_sync = True

    api_url = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
    detail_url = "https://www.youthcenter.go.kr/youthPolicy/ythPlcyTotalSearch/ythPlcyDetail"
    page_size = 500

    #: 본문에 넣을 필드(라벨, 키). 매칭의 관심분야 텍스트 검색에 쓰인다.
    _BODY_FIELDS = (
        ("설명", "plcyExplnCn"),
        ("지원내용", "plcySprtCn"),
        ("신청자격", "addAplyQlfcCndCn"),
        ("신청방법", "plcyAplyMthdCn"),
        ("심사방법", "srngMthdCn"),
        ("제출서류", "sbmsnDcmntCn"),
    )

    def preflight(self, respect_robots: bool = True) -> None:
        # 공식 API라 robots.txt 대상이 아니다. 키만 확인한다.
        if not settings.youthcenter_api_key:
            raise ComplianceError(f"[{self.platform}] YOUTHCENTER_API_KEY 미설정")

    def _to_raw(self, item: dict) -> RawPosting | None:
        name = (item.get("plcyNm") or "").strip()
        plcy_no = item.get("plcyNo")
        if not name or not plcy_no or item.get("aplyPrdSeCd") == "0057003":
            return None

        # 신청 마감일, 없으면(상시) 사업 종료일
        m = re.search(r"~\s*(\d{8})", item.get("aplyYmd") or "")
        end = m.group(1) if m else (item.get("bizPrdEndYmd") or "").strip()
        deadline = _parse_kst(end, "%Y%m%d") if end else None
        if deadline:
            deadline = deadline.replace(hour=23, minute=59)

        regions = _regions_from_zip(item.get("zipCd") or "")
        body = "\n".join(
            f"[{label}] {item[key].strip()}"
            for label, key in self._BODY_FIELDS
            if (item.get(key) or "").strip()
        )

        return RawPosting(
            title=name,
            source_url=f"{self.detail_url}/{plcy_no}",
            source_platform=self.platform,
            source_type=self.source_type,
            category=Category.SCHOLARSHIP if "장학" in name else Category.GOV_BENEFIT,
            organization=item.get("sprvsnInstCdNm") or item.get("operInstCdNm") or None,
            deadline_raw=end or None,  # 변경 감지 해시에 마감일 변경이 잡히게
            deadline_at=deadline,
            posted_at=_parse_kst(item.get("frstRegDt"), "%Y-%m-%d %H:%M:%S"),
            eligibility={"region": regions} if regions else {},
            body_text=body,
        )

    def fetch(self) -> list[RawPosting]:
        import time

        import httpx

        results: list[RawPosting] = []
        received = total = 0
        with httpx.Client(timeout=30) as client:
            page = 1
            while True:
                resp = client.get(
                    self.api_url,
                    params={
                        "apiKeyNm": settings.youthcenter_api_key,
                        "pageNum": page,
                        "pageSize": self.page_size,
                        "rtnType": "json",
                    },
                )
                # raise_for_status 메시지에는 키가 든 URL이 찍히므로 직접 만든다.
                if resp.status_code != 200:
                    raise RuntimeError(f"youthcenter HTTP {resp.status_code}")
                payload = resp.json()
                if payload.get("resultCode") != 200:
                    raise RuntimeError(f"youthcenter resultCode={payload.get('resultCode')}")

                data = payload.get("result") or {}
                items = data.get("youthPolicyList") or []
                received += len(items)
                results.extend(r for r in map(self._to_raw, items) if r)

                total = (data.get("pagging") or {}).get("totCount", 0)
                if not items or page * self.page_size >= total:
                    break
                page += 1
                time.sleep(settings.crawl_default_delay_sec)

        # 목록에서 빠진 정책은 삭제되므로, 덜 받은 채로 동기화하면 멀쩡한 공고가 지워진다.
        if received < total:
            raise RuntimeError(f"youthcenter incomplete: {received}/{total}")
        return results


#: 본문 텍스트를 뽑을 수 있는 첨부 확장자
_TEXT_EXTS = (".hwpx", ".hwp", ".pdf", ".docx", ".txt")
#: 신청서 양식류 첨부. 구조화 추출은 본문 앞부분만 읽으므로 모집요강 뒤로 보낸다.
_FORM_HINTS = ("서식", "양식", "신청서", "지원서", "동의서", "추천서")


class KhuScholarshipCrawler(BaseCrawler):
    """경희대학교 장학공지 게시판.

    robots.txt 실사(2026-08): `Disallow: /cms/`, `/upload/` 뿐이라 게시판
    경로(/janghak/user/bbs/)는 허용된다.

    목록 구조(확인됨):
        tr > td(구분) / td(카테고리: 공통_교외장학|공통_교내장학) / td(제목)
             / td(첨부) / td(등록일 YYYY-MM-DD)
        상세는 view.do?menuNo=..&boardId=.. (GET 가능), 본문은 div.bbs-view_c

    목록에는 마감일이 없다. fetch()는 목록(제목·등록일)만 가져오고, 상위
    파이프라인이 새 글에 한해 fetch_detail()로 본문·첨부를 받아 마감일을 뽑는다.
    제목에 마감 표기가 있으면 그것을 먼저 쓴다.
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

    def fetch_detail(self, raw: RawPosting) -> None:
        """상세 본문 HTML 텍스트 + 텍스트 첨부 전부를 body_text에 붙인다.

        첨부는 전부 읽는다: 첫 첨부가 신청서 양식이고 모집요강은 그 뒤인 공고가 흔하다.
        본문이 이미지뿐이고 텍스트 첨부도 없으면 채울 것이 없다(OCR 미적용).
        """
        import time

        import httpx
        from bs4 import BeautifulSoup

        from app.utils.file_parser import extract_text_from_bytes

        parts: list[str] = []
        names: list[str] = []
        headers = {"User-Agent": self.user_agent}
        try:
            with httpx.Client(timeout=25, follow_redirects=True, headers=headers) as client:
                r = client.get(raw.source_url)
                if r.status_code != 200 or "에러안내" in r.text:
                    return
                soup = BeautifulSoup(r.text, "lxml")
                view = soup.select_one("div.bbs-view_c")
                if view:
                    parts.append(view.get_text("\n", strip=True))

                links = []
                for a in soup.select('a[href*="fileDown"]'):
                    nm = " ".join(a.get_text(" ", strip=True).split())
                    if nm.lower().endswith(_TEXT_EXTS):
                        links.append((nm, a.get("href") or ""))
                links.sort(key=lambda link: any(h in link[0] for h in _FORM_HINTS))

                for nm, href in links:
                    time.sleep(settings.crawl_default_delay_sec)
                    fr = client.get(href if href.startswith("http") else f"{self.base_url}{href}")
                    if fr.status_code != 200 or not fr.content:
                        continue
                    try:
                        parts.append(extract_text_from_bytes(fr.content, nm))
                        names.append(nm)
                    except Exception:  # noqa: BLE001 - 첨부 하나가 깨져도 나머지는 읽는다
                        logger.warning("khu attachment parse failed: %s", nm)
        except Exception:  # noqa: BLE001 - 상세 실패가 목록 수집을 막지 않게
            logger.warning("khu detail fetch failed: %s", raw.source_url)

        text = "\n".join(p for p in parts if p)
        if text:
            raw.body_text = f"{raw.body_text}\n{text}"
        if names:
            raw.required_documents = names

    def fetch(self) -> list[RawPosting]:
        import time as _time

        import httpx
        from bs4 import BeautifulSoup

        from app.crawlers.date_parser import normalize_deadline

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

                    # 제목에 마감 표기가 있으면 사용(없으면 None → 상세 본문에서 추출)
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

        return results
