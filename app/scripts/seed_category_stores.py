"""카테고리별 매장 시드(편의점 외: 카페·음식점·마트·베이커리·H&B).

기존 seed_stores.py는 legacy/app.js의 편의점 35개를 넣는다. 이 스크립트는
지도 카테고리 필터를 의미있게 만들기 위해 카페/음식점/마트 등 매장을
경희대·회기 일대 좌표로 추가한다.

브랜드는 card_benefits의 brand_key와 일치시켜, 매장 클릭 시 카드 혜택이
함께 조인되도록 한다(스타벅스·이마트·파리바게뜨 등).

간편결제(StoreOffer)는 이 카테고리엔 기본으로 넣지 않는다(편의점 전용 예시였음).
카드 혜택은 브랜드 조인으로 자동 표시된다.

사용:
    python -m app.scripts.seed_category_stores
    python -m app.scripts.seed_category_stores --clear   # 이 스크립트가 넣은 매장만 삭제
"""
from __future__ import annotations

import json
import sys

from sqlalchemy import delete, select

from app.core.db import SessionLocal, init_db
from app.models.store import Store, StoreCategory

# 경희대·회기·외대 일대 실제 브랜드 매장(좌표는 인근 실측 근사값).
# brand는 card_benefits.brand_key와 일치해야 카드 혜택이 조인된다.
_STORES: list[dict] = [
    # --- 카페 ---
    {"brand": "스타벅스", "branch": "경희대점", "category": StoreCategory.CAFE, "address": "회기로 195", "lat": 37.591749, "lng": 127.051856, "mark": "★", "color": "#00704a"},
    {"brand": "스타벅스", "branch": "회기역점", "category": StoreCategory.CAFE, "address": "회기로 118", "lat": 37.589655, "lng": 127.057882, "mark": "★", "color": "#00704a"},
    {"brand": "메가MGC커피", "branch": "경희대정문점", "category": StoreCategory.CAFE, "address": "경희대로 26", "lat": 37.592920, "lng": 127.051760, "mark": "M", "color": "#3a1d1d"},
    {"brand": "메가MGC커피", "branch": "외대앞점", "category": StoreCategory.CAFE, "address": "휘경로 8", "lat": 37.595520, "lng": 127.062010, "mark": "M", "color": "#3a1d1d"},
    # --- 베이커리 ---
    {"brand": "파리바게뜨", "branch": "경희대점", "category": StoreCategory.BAKERY, "address": "회기로 201", "lat": 37.592050, "lng": 127.051200, "mark": "P", "color": "#0a4a9e"},
    {"brand": "뚜레쥬르", "branch": "회기역점", "category": StoreCategory.BAKERY, "address": "회기로 121", "lat": 37.589900, "lng": 127.057200, "mark": "T", "color": "#e60012"},
    # --- 음식점 ---
    {"brand": "아웃백", "branch": "청량리점", "category": StoreCategory.RESTAURANT, "address": "왕산로 214", "lat": 37.580230, "lng": 127.047560, "mark": "🥩", "color": "#8b1a1a"},
    {"brand": "VIPS", "branch": "청량리점", "category": StoreCategory.RESTAURANT, "address": "왕산로 205", "lat": 37.580100, "lng": 127.046800, "mark": "V", "color": "#c8102e"},
    # --- 마트 ---
    {"brand": "이마트", "branch": "청량리점", "category": StoreCategory.MART, "address": "왕산로 214", "lat": 37.580400, "lng": 127.047900, "mark": "e", "color": "#ffd200"},
    {"brand": "홈플러스 익스프레스", "branch": "회기점", "category": StoreCategory.MART, "address": "회기로 25", "lat": 37.590500, "lng": 127.056000, "mark": "H", "color": "#e2231a"},
    {"brand": "롯데슈퍼", "branch": "이문점", "category": StoreCategory.MART, "address": "이문로 88", "lat": 37.594300, "lng": 127.061500, "mark": "L", "color": "#da291c"},
    # --- H&B ---
    {"brand": "올리브영", "branch": "경희대점", "category": StoreCategory.HNB, "address": "회기로 199", "lat": 37.591950, "lng": 127.051500, "mark": "O", "color": "#8bc53f"},
]

_SEED_BRANCH_TAG = None  # 구분자 불필요: brand+branch 조합으로 식별


def clear(db) -> int:
    keys = [(s["brand"], s["branch"]) for s in _STORES]
    n = 0
    for brand, branch in keys:
        r = db.execute(
            delete(Store).where(Store.brand == brand, Store.branch == branch)
        )
        n += r.rowcount or 0
    db.commit()
    return n


def seed() -> dict:
    init_db()
    db = SessionLocal()
    created = 0
    updated = 0
    try:
        for s in _STORES:
            existing = db.scalar(
                select(Store).where(Store.brand == s["brand"], Store.branch == s["branch"])
            )
            if existing is None:
                db.add(Store(**s))
                created += 1
            else:
                existing.category = s["category"]
                existing.address = s["address"]
                existing.lat, existing.lng = s["lat"], s["lng"]
                existing.mark, existing.color = s["mark"], s["color"]
                updated += 1
        db.commit()
    finally:
        db.close()
    return {"created": created, "updated": updated}


if __name__ == "__main__":
    if "--clear" in sys.argv:
        db = SessionLocal()
        try:
            print(json.dumps({"deleted": clear(db)}, ensure_ascii=False))
        finally:
            db.close()
    else:
        print(json.dumps(seed(), ensure_ascii=False, indent=2))
