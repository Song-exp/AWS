"""로컬 실행에 필요한 데이터를 한 번에 준비한다.

기본 실행은 외부 네트워크 없이 재현 가능하도록 샘플 장학금을 사용한다.
실제 공고가 필요하면 ``--scholarships crawl``을, 기존 장학금을 그대로
유지하려면 ``--scholarships skip``을 지정한다.

사용:
    python -m app.scripts.init_all
    python -m app.scripts.init_all --scholarships crawl
    python -m app.scripts.init_all --scholarships crawl --month 2026-08 --month 2026-09
    python -m app.scripts.init_all --scholarships skip

각 시드가 upsert 방식이라 같은 명령을 여러 번 실행해도 중복 적재되지 않는다.
"""
from __future__ import annotations

import argparse
import json
from typing import Literal

from app.core.db import SessionLocal, init_db
from app.crawlers.registry import run_monthly_update
from app.models.crawl_run import CrawlRunStatus
from app.scripts.seed_boards import seed_boards
from app.scripts.seed_card_benefits import seed as seed_card_benefits
from app.scripts.seed_category_stores import seed as seed_category_stores
from app.scripts.seed_sample_scholarships import seed as seed_sample_scholarships
from app.scripts.seed_stores import seed as seed_stores
from app.scripts.seed_local_benefits import seed as seed_local_benefits

ScholarshipMode = Literal["sample", "crawl", "skip"]


def _month(value: str) -> tuple[int, int]:
    """CLI의 YYYY-MM 값을 (연, 월)로 변환한다."""
    try:
        year_text, month_text = value.split("-", 1)
        year, month = int(year_text), int(month_text)
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("월은 YYYY-MM 형식이어야 합니다.") from exc
    if year < 2000 or not 1 <= month <= 12:
        raise argparse.ArgumentTypeError("유효한 연도와 월을 입력하세요(예: 2026-09).")
    return year, month


def _crawl_scholarships(target_months: set[tuple[int, int]] | None) -> dict:
    db = SessionLocal()
    try:
        run = run_monthly_update(
            db,
            trigger="init_all",
            target_months=target_months,
        )
        return {
            "mode": "crawl",
            "run_id": run.id,
            "status": run.status.value,
            "target_months": run.target_months,
            "fetched": run.total_fetched,
            "saved": run.total_saved,
            "expired": run.total_expired,
            "per_platform": run.per_platform,
            "error": run.error,
        }
    finally:
        db.close()


def initialize_all(
    scholarship_mode: ScholarshipMode = "sample",
    target_months: set[tuple[int, int]] | None = None,
) -> dict:
    """매장·카테고리 매장·카드 혜택·장학금을 순서대로 준비한다."""
    init_db()
    result = {
        "stores": seed_stores(),
        "category_stores": seed_category_stores(),
        "local_benefits": seed_local_benefits(),
        "card_benefits": seed_card_benefits(),
        "boards": seed_boards(),
    }

    if scholarship_mode == "sample":
        result["scholarships"] = {
            "mode": "sample",
            **seed_sample_scholarships(),
        }
    elif scholarship_mode == "crawl":
        result["scholarships"] = _crawl_scholarships(target_months)
    else:
        result["scholarships"] = {"mode": "skip"}

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="서비스 실행에 필요한 매장·카드·장학금 데이터를 한 번에 준비합니다."
    )
    parser.add_argument(
        "--scholarships",
        choices=("sample", "crawl", "skip"),
        default="sample",
        help="장학금 준비 방식(기본: sample)",
    )
    parser.add_argument(
        "--month",
        action="append",
        type=_month,
        default=None,
        help="crawl 대상 월(YYYY-MM, 여러 번 지정 가능)",
    )
    args = parser.parse_args()

    if args.month and args.scholarships != "crawl":
        parser.error("--month는 --scholarships crawl과 함께 사용해야 합니다.")

    result = initialize_all(
        scholarship_mode=args.scholarships,
        target_months=set(args.month) if args.month else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    scholarship = result["scholarships"]
    if scholarship.get("status") == CrawlRunStatus.FAILED.value:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
