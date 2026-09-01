"""지도 서비스 검증(주변 매장 · 최적 결제수단 추천)."""
from __future__ import annotations

KHU_LAT, KHU_LNG = 37.5966, 127.0525


def _by_brand(items):
    return {i["brand"]: i for i in items}


def test_radius_excludes_far_stores(client, seed_stores):
    r = client.get("/stores/nearby",
                   params={"lat": KHU_LAT, "lng": KHU_LNG, "radius_m": 2000})
    assert r.status_code == 200
    branches = {i["branch"] for i in r.json()}
    assert "경희대점" in branches
    assert "부산서면점" not in branches


def test_distance_is_computed_and_sorted(client, seed_stores):
    items = client.get("/stores/nearby",
                       params={"lat": KHU_LAT, "lng": KHU_LNG,
                               "radius_m": 2000, "sort": "distance"}).json()
    distances = [i["distance_m"] for i in items]
    assert all(d is not None for d in distances)
    assert distances == sorted(distances)


def test_category_filter(client, seed_stores):
    items = client.get("/stores/nearby",
                       params={"lat": KHU_LAT, "lng": KHU_LNG, "category": "cafe"}).json()
    assert {i["category"] for i in items} == {"cafe"}


def test_best_deal_picks_simple_pay_when_higher(client, seed_stores):
    """CU: 카카오 10%만 있다 → 간편결제가 최적."""
    items = client.get("/stores/nearby",
                       params={"lat": KHU_LAT, "lng": KHU_LNG, "radius_m": 2000}).json()
    cu = _by_brand(items)["CU"]
    assert cu["best_deal"]["kind"] == "simple_pay"
    assert cu["best_deal"]["discount_rate"] == 10.0


def test_best_deal_picks_card_when_higher(client, seed_stores):
    """GS25: 네이버 5% vs 카드 20% → 카드가 최적.

    두 혜택은 '간편결제 제외' 조건이라 합산하면 안 되고, 더 유리한 쪽만
    골라야 한다. 합산 로직이 들어오면 25%가 되어 이 테스트가 깨진다.
    """
    items = client.get("/stores/nearby",
                       params={"lat": KHU_LAT, "lng": KHU_LNG, "radius_m": 2000}).json()
    gs = _by_brand(items)["GS25"]
    assert gs["best_deal"]["kind"] == "card"
    assert gs["best_deal"]["discount_rate"] == 20.0


def test_card_benefits_hidden_when_user_has_no_such_card(client, seed_stores):
    """보유하지 않은 카드 혜택을 최적 추천으로 보여주면 안 된다."""
    items = client.get("/stores/nearby",
                       params={"lat": KHU_LAT, "lng": KHU_LNG, "radius_m": 2000,
                               "card_ids": 999999}).json()
    gs = _by_brand(items)["GS25"]
    assert gs["card_benefits"] == []
    assert gs["best_deal"]["kind"] == "simple_pay"   # 카드 빠지면 네이버 5%


def test_pay_filter_keeps_stores_without_offers(client, seed_stores):
    """카페처럼 간편결제 혜택이 없는 매장은 pay 필터로 지워지면 안 된다.

    지도에서 매장 자체가 사라지면 사용자는 '문 닫았나?'로 읽는다.
    """
    items = client.get("/stores/nearby",
                       params={"lat": KHU_LAT, "lng": KHU_LNG,
                               "radius_m": 2000, "pay": "kakao"}).json()
    brands = {i["brand"] for i in items}
    assert "CU" in brands          # 카카오 혜택 보유
    assert "GS25" not in brands    # 네이버만 보유 → 제외
    assert "스타벅스" in brands     # offer 자체가 없음 → 유지


def test_meta_options_available_for_onboarding(client, seed_stores):
    """온보딩 화면이 이 응답에 의존한다. 비면 카드 선택이 불가능해진다."""
    r = client.get("/meta/options")
    assert r.status_code == 200
    body = r.json()
    assert body["cards"], "카드 옵션이 비었다"
