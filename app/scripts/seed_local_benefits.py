"""다운로드 원본에서 정규화한 제휴·지역화폐 가맹점 1,213건 시드."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal, init_db
from app.models.local_benefit import LocalBenefitMerchant
from app.models.store import StoreCategory

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "local_benefits.json"


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def seed(path: str | Path = _DATA_PATH) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload["records"]
    init_db()
    db = SessionLocal()
    created = 0
    updated = 0
    try:
        existing = {
            row.source_key: row
            for row in db.scalars(select(LocalBenefitMerchant)).all()
        }
        for item in records:
            values = {
                "merchant_name": item["merchant_name"],
                "category": StoreCategory(item["category"]),
                "category_label": item.get("category_label"),
                "address": item.get("address"),
                "search_query": item["search_query"],
                "source_type": item["source_type"],
                "programs": list(item.get("programs") or []),
                "credentials": list(item.get("credentials") or []),
                "requires": item.get("requires"),
                "benefit_text": item["benefit_text"],
                "discount_type": item.get("discount_type"),
                "discount_value": item.get("discount_value"),
                "min_spend": item.get("min_spend"),
                "max_amount": item.get("max_amount"),
                "conditions": item.get("conditions"),
                "valid_to": _date(item.get("valid_to")),
                "confidence": item.get("confidence"),
                "source_url": item.get("source_url"),
                "is_active": True,
            }
            row = existing.get(item["source_key"])
            if row is None:
                db.add(LocalBenefitMerchant(source_key=item["source_key"], **values))
                created += 1
            else:
                for key, value in values.items():
                    setattr(row, key, value)
                updated += 1
        db.commit()
    finally:
        db.close()
    return {
        "source_records": len(records),
        "source_counts": payload.get("source_counts", {}),
        "created": created,
        "updated": updated,
    }


if __name__ == "__main__":
    print(json.dumps(seed(), ensure_ascii=False, indent=2))
