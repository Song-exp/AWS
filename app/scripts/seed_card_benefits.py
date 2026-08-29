"""카드 혜택 시드 스크립트.

두 파일을 함께 사용한다:
  - card_benefits_202608.json      : 카드 마스터(발급사·발급상태) + 이벤트 상세(url/cap/중복여부)
  - card_benefits_flat_202608.json : 카드 × 가맹점 × 할인 평탄화 행(조인용)

flat 행을 기준으로 적재하고, cards 파일에서 카드 메타와 이벤트 상세를
찾아 보강한다. 복합 가맹점('GS25 / GS더프레시')은 브랜드별로 분리 적재해
지도 매장과 브랜드 단위로 조인되게 한다.

사용:
    python -m app.scripts.seed_card_benefits
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date, datetime

from sqlalchemy import select

from app.core.db import SessionLocal, init_db
from app.models.card import BenefitType, Card, CardBenefit, Confidence, PeriodType
from app.services.card_normalize import (
    detect_excludes_simple_pay,
    normalize_merchant,
    parse_benefit_value,
    parse_min_payment,
    period_to_dates,
)

_FLAT = os.path.join("data", "card_benefits_flat_202608.json")
_CARDS = os.path.join("data", "card_benefits_202608.json")


def _dedup_key(card_name: str, merchant: str, brand: str, text: str, period: str) -> str:
    raw = f"{card_name}|{merchant}|{brand}|{text}|{period}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def _load_card_master(cards_path: str) -> dict:
    """카드명 -> {issuer, issuance_status, card_key, events:[...]}"""
    if not os.path.exists(cards_path):
        return {}
    data = json.load(open(cards_path, encoding="utf-8"))
    master: dict[str, dict] = {}
    for c in data.get("cards", []):
        name = c.get("card_name")
        if not name:
            continue
        events = []
        for key in ("august_2026_monthly", "august_2026_week4", "always_on_benefits"):
            for ev in c.get(key) or []:
                events.append(ev)
        master[name] = {
            "card_key": c.get("card_id") or name,
            "issuer": c.get("issuer"),
            "issuance_status": c.get("issuance_status"),
            "events": events,
        }
    return master


def _find_event_detail(master_entry: dict | None, merchant_raw: str, benefit_text: str | None) -> dict:
    """cards 파일 이벤트 목록에서 url/cap/중복여부를 찾아 보강."""
    if not master_entry:
        return {}
    for ev in master_entry.get("events", []):
        if not isinstance(ev, dict):
            continue
        merchants = ev.get("merchants") or []
        # merchants 원소가 문자열이 아닌 경우(dict 등)도 있어 방어적으로 직렬화
        parts: list[str] = []
        for m in merchants:
            if isinstance(m, str):
                parts.append(m)
            elif isinstance(m, dict):
                parts.append(" ".join(str(v) for v in m.values()))
            else:
                parts.append(str(m))
        m_text = " ".join(parts) if parts else str(ev.get("merchant") or "")
        benefit = str(ev.get("benefit") or "")
        # 가맹점 또는 혜택 텍스트가 겹치면 같은 이벤트로 판단
        token = merchant_raw.split("/")[0].split("·")[0].strip()
        if token and token in m_text:
            return ev
        if benefit_text and benefit and benefit_text[:8] in benefit:
            return ev
    return {}


def _get_or_create_card(db, card_name: str, master: dict) -> Card:
    entry = master.get(card_name)
    card_key = (entry or {}).get("card_key") or card_name
    row = db.scalar(select(Card).where(Card.card_key == card_key))
    if row is None:
        row = Card(
            card_key=card_key,
            card_name=card_name,
            issuer=(entry or {}).get("issuer"),
            issuance_status=(entry or {}).get("issuance_status"),
        )
        db.add(row)
        db.flush()
    return row


def _benefit_type(raw: str | None) -> BenefitType:
    try:
        return BenefitType(str(raw))
    except ValueError:
        return BenefitType.UNVERIFIED


def _confidence(raw: str | None) -> Confidence:
    try:
        return Confidence(str(raw))
    except ValueError:
        return Confidence.UNVERIFIED


def _period_type(raw: str | None) -> PeriodType | None:
    try:
        return PeriodType(str(raw))
    except ValueError:
        return None


def seed(flat_path: str = _FLAT, cards_path: str = _CARDS) -> dict:
    if not os.path.exists(flat_path):
        raise FileNotFoundError(f"{flat_path} 를 찾을 수 없습니다.")

    flat = json.load(open(flat_path, encoding="utf-8"))
    rows = flat.get("rows", [])
    as_of_raw = (flat.get("meta") or {}).get("as_of_date")
    as_of = None
    if as_of_raw:
        try:
            as_of = datetime.strptime(as_of_raw, "%Y-%m-%d").date()
        except ValueError:
            as_of = None

    master = _load_card_master(cards_path)

    init_db()
    db = SessionLocal()
    created = 0
    updated = 0
    skipped_expired = 0
    unmatched = 0
    try:
        for r in rows:
            btype = _benefit_type(r.get("benefit_type"))
            if btype == BenefitType.EXPIRED:
                skipped_expired += 1
                continue

            merchant_raw = r.get("merchant") or ""
            brands = normalize_merchant(merchant_raw)
            if not brands:
                # 지도 매칭 대상이 아닌 혜택도 brand_key=None으로 보관(목록 노출용)
                brands = [None]
                unmatched += 1

            card = _get_or_create_card(db, r.get("card") or "(미상)", master)
            detail = _find_event_detail(master.get(r.get("card")), merchant_raw, r.get("benefit_text"))

            vmin, vmax = parse_benefit_value(r.get("benefit_value"))
            min_krw, min_raw = parse_min_payment(r.get("min_payment"))
            ptype = _period_type(r.get("period_type"))
            vfrom, vto = period_to_dates(r.get("period_type"), r.get("period") or detail.get("period"))
            conditions = r.get("conditions") or []

            for brand in brands:
                key = _dedup_key(
                    card.card_name,
                    merchant_raw,
                    brand or "-",
                    str(r.get("benefit_text")),
                    str(r.get("period")),
                )
                existing = db.scalar(select(CardBenefit).where(CardBenefit.dedup_key == key))
                if existing is None:
                    db.add(
                        CardBenefit(
                            card_id=card.id,
                            dedup_key=key,
                            merchant_raw=merchant_raw,
                            brand_key=brand,
                            category=r.get("category"),
                            benefit_type=btype,
                            value_min=vmin,
                            value_max=vmax,
                            benefit_text=r.get("benefit_text"),
                            min_payment_krw=min_krw,
                            min_payment_raw=min_raw,
                            cap_text=detail.get("cap"),
                            period_type=ptype,
                            period_text=r.get("period"),
                            valid_from=vfrom,
                            valid_to=vto,
                            conditions=conditions,
                            excludes_simple_pay=detect_excludes_simple_pay(conditions),
                            stackable_note=detail.get("stackable_with_always_on"),
                            confidence=_confidence(r.get("confidence")),
                            source_url=detail.get("url"),
                            source_as_of=as_of,
                            is_active=True,
                        )
                    )
                    created += 1
                else:
                    existing.value_min, existing.value_max = vmin, vmax
                    existing.benefit_text = r.get("benefit_text")
                    existing.conditions = conditions
                    existing.excludes_simple_pay = detect_excludes_simple_pay(conditions)
                    existing.valid_from, existing.valid_to = vfrom, vto
                    existing.source_url = detail.get("url") or existing.source_url
                    updated += 1
        db.commit()
    finally:
        db.close()

    return {
        "flat_rows": len(rows),
        "created_benefits": created,
        "updated_benefits": updated,
        "skipped_expired": skipped_expired,
        "rows_without_brand_match": unmatched,
    }


if __name__ == "__main__":
    flat = sys.argv[1] if len(sys.argv) > 1 else _FLAT
    cards = sys.argv[2] if len(sys.argv) > 2 else _CARDS
    print(json.dumps(seed(flat, cards), ensure_ascii=False, indent=2))
