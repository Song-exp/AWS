"""매장·혜택 시드 스크립트.

기존 프론트(app.js)에 하드코딩된 stores/standardOffers를 파싱해 DB로 이관한다.
수동 전사 오류를 막기 위해 app.js를 직접 읽어 파싱한다.

사용:
    python -m app.scripts.seed_stores            # 기본: legacy/app.js
    python -m app.scripts.seed_stores path/to/app.js
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date

from sqlalchemy import select

from app.core.db import SessionLocal, init_db
from app.models.store import PayMethod, Store, StoreOffer

_STORE_BLOCK = re.compile(r"const stores = \[(.*?)\n\];", re.S)
_OFFERS_BLOCK = re.compile(r"const standardOffers = \{(.*?)\n\};", re.S)
_ITEM = re.compile(r"\{[^{}]*\}")


def _js_field(block: str, key: str) -> str | None:
    """JS 객체 리터럴에서 key의 값을 추출(문자열/숫자)."""
    m = re.search(rf"{key}:\s*'([^']*)'", block)
    if m:
        return m.group(1)
    m = re.search(rf"{key}:\s*([-\d.]+)", block)
    return m.group(1) if m else None


def parse_stores(js_src: str) -> list[dict]:
    block = _STORE_BLOCK.search(js_src)
    if not block:
        raise ValueError("app.js에서 stores 배열을 찾지 못했습니다.")
    stores: list[dict] = []
    for item in _ITEM.findall(block.group(1)):
        brand = _js_field(item, "brand")
        branch = _js_field(item, "branch")
        lat = _js_field(item, "lat")
        lng = _js_field(item, "lng")
        if not (brand and branch and lat and lng):
            continue
        stores.append(
            {
                "brand": brand,
                "branch": branch,
                "address": _js_field(item, "address"),
                "mark": _js_field(item, "mark"),
                "color": _js_field(item, "color"),
                "lat": float(lat),
                "lng": float(lng),
            }
        )
    return stores


def parse_offers(js_src: str) -> dict[str, tuple[int, str]]:
    """standardOffers = { kakao: [5, '조건'], ... } 파싱."""
    block = _OFFERS_BLOCK.search(js_src)
    if not block:
        return {}
    offers: dict[str, tuple[int, str]] = {}
    for m in re.finditer(r"(\w+):\s*\[\s*(\d+)\s*,\s*'([^']*)'\s*\]", block.group(1)):
        offers[m.group(1)] = (int(m.group(2)), m.group(3))
    return offers


_DEFAULT_JS = os.path.join("legacy", "app_mvp.js") if os.path.exists(os.path.join("legacy", "app_mvp.js")) else os.path.join("legacy", "app.js")


def seed(js_path: str | None = None) -> dict:
    if js_path is None:
        js_path = _DEFAULT_JS
    if not os.path.exists(js_path):
        fallback = os.path.join("legacy", "app_mvp.js")
        if os.path.exists(fallback):
            js_path = fallback
        else:
            raise FileNotFoundError(f"{js_path} 를 찾을 수 없습니다.")
    src = open(js_path, encoding="utf-8").read()

    try:
        stores = parse_stores(src)
        offers = parse_offers(src)
    except ValueError:
        fallback = os.path.join("legacy", "app_mvp.js")
        if os.path.exists(fallback) and js_path != fallback:
            src = open(fallback, encoding="utf-8").read()
            stores = parse_stores(src)
            offers = parse_offers(src)
        else:
            raise

    init_db()
    db = SessionLocal()
    created_stores = 0
    created_offers = 0
    try:
        for s in stores:
            existing = db.scalar(
                select(Store).where(Store.brand == s["brand"], Store.branch == s["branch"])
            )
            if existing is None:
                row = Store(**s)
                db.add(row)
                db.flush()  # id 확보
                created_stores += 1
            else:
                row = existing
                # 좌표/주소 갱신
                row.address = s["address"]
                row.lat, row.lng = s["lat"], s["lng"]
                row.mark, row.color = s["mark"], s["color"]

            for method_key, (rate, condition) in offers.items():
                try:
                    method = PayMethod(method_key)
                except ValueError:
                    continue
                dup = db.scalar(
                    select(StoreOffer).where(
                        StoreOffer.store_id == row.id, StoreOffer.pay_method == method
                    )
                )
                if dup is None:
                    db.add(
                        StoreOffer(
                            store_id=row.id,
                            pay_method=method,
                            discount_rate=rate,
                            condition_text=condition,
                            valid_from=date.today().replace(day=1),
                            is_active=True,
                            is_sample=True,
                        )
                    )
                    created_offers += 1
                else:
                    # 사람이 실제 값으로 고친 혜택은 시드가 덮어쓰지 않는다.
                    if dup.is_sample or dup.discount_rate == rate:
                        dup.discount_rate = rate
                        dup.condition_text = condition
                        dup.is_sample = True
        db.commit()
    finally:
        db.close()

    return {
        "parsed_stores": len(stores),
        "parsed_pay_methods": len(offers),
        "created_stores": created_stores,
        "created_offers": created_offers,
    }


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_JS
    print(json.dumps(seed(path), ensure_ascii=False, indent=2))
