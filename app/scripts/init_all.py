"""로컬 실행에 필요한 데이터를 한 번에 준비한다.

기본 실행은 외부 네트워크 없이 재현 가능하도록 샘플 장학금을 사용한다.
실제 공고가 필요하면 ``--scholarships crawl``을, 기존 장학금을 그대로
유지하려면 ``--scholarships skip``을 지정한다.

사용:
    python -m app.scripts.init_all
    python -m app.scripts.init_all --scholarships crawl
    python -m app.scripts.init_all --scholarships skip

각 시드가 upsert 방식이라 같은 명령을 여러 번 실행해도 중복 적재되지 않는다.
"""
from __future__ import annotations

import argparse
import json
from typing import Literal

from app.core.db import SessionLocal, init_db
from app.crawlers.registry import run_daily_update
from app.models.crawl_run import CrawlRunStatus
from app.scripts.seed_boards import seed_boards
from app.scripts.seed_card_benefits import seed as seed_card_benefits
from app.scripts.seed_category_stores import seed as seed_category_stores
from app.scripts.seed_sample_scholarships import seed as seed_sample_scholarships
from app.scripts.seed_stores import seed as seed_stores
from app.scripts.seed_local_benefits import seed as seed_local_benefits

ScholarshipMode = Literal["sample", "crawl", "skip"]


def _crawl_scholarships() -> dict:
    db = SessionLocal()
    try:
        run = run_daily_update(db, trigger="init_all")
        return {
            "mode": "crawl",
            "run_id": run.id,
            "status": run.status.value,
            "fetched": run.total_fetched,
            "saved": run.total_saved,
            "expired": run.total_expired,
            "per_platform": run.per_platform,
            "error": run.error,
        }
    finally:
        db.close()


def initialize_all(scholarship_mode: ScholarshipMode = "sample") -> dict:
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
        result["scholarships"] = _crawl_scholarships()
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
    args = parser.parse_args()

    result = initialize_all(scholarship_mode=args.scholarships)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    scholarship = result["scholarships"]
    if scholarship.get("status") == CrawlRunStatus.FAILED.value:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
