import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { fetchNearbyStores, fetchOptions } from "../api";
import type {
  CardBenefit,
  CategoryOption,
  PayMethod,
  Store,
  StoreCategory,
  UserProfileLocal,
} from "../types";
import { useKakaoLoader } from "../useKakaoLoader";

const PAY_LABELS: Record<PayMethod, string> = {
  kakao: "카카오페이",
  toss: "토스페이",
  naver: "네이버페이",
};

const ALL_PAYS: PayMethod[] = ["kakao", "toss", "naver"];
const DEFAULT_CENTER = { lat: 37.5938, lng: 127.0564 };

const CATEGORY_META: Record<
  StoreCategory,
  { label: string; color: string; icon: string }
> = {
  convenience: { label: "편의점", color: "#eab308", icon: "24" },
  cafe: { label: "카페", color: "#f97316", icon: "☕" },
  restaurant: { label: "음식점", color: "#ef4444", icon: "🍽" },
  mart: { label: "마트", color: "#22c55e", icon: "🛒" },
  bakery: { label: "베이커리", color: "#a855f7", icon: "🥐" },
  hnb: { label: "H&B", color: "#ec4899", icon: "+" },
  other: { label: "기타", color: "#6b7280", icon: "•" },
};

function formatDistance(m: number | null): string {
  if (m === null) return "";
  if (m < 1000) return `${Math.max(10, Math.round(m / 10) * 10)}m`;
  return `${(m / 1000).toFixed(1)}km`;
}

function topRate(store: Store): number {
  return Math.max(store.max_discount_rate, store.max_card_discount_rate);
}

function benefitLabel(benefit: CardBenefit): string {
  if (benefit.benefit_text) return benefit.benefit_text;
  if (benefit.benefit_type === "percent" && benefit.value_min !== null) {
    return benefit.value_max && benefit.value_max !== benefit.value_min
      ? `${benefit.value_min}~${benefit.value_max}%`
      : `${benefit.value_min}%`;
  }
  if (benefit.benefit_type === "amount" && benefit.value_min !== null) {
    return `${benefit.value_min.toLocaleString()}원 할인`;
  }
  return "행사 진행";
}

interface Props {
  profile: UserProfileLocal | null;
}

export default function MapPage({ profile }: Props) {
  const { ready, error: sdkError } = useKakaoLoader(
    import.meta.env.VITE_KAKAO_MAP_KEY
  );
  const mapRef = useRef<HTMLDivElement>(null);
  const mapObj = useRef<any>(null);
  const mapEl = useRef<HTMLDivElement | null>(null);
  const overlays = useRef<any[]>([]);

  const configuredPays = useMemo<PayMethod[]>(
    () =>
      profile && profile.payMethods.length > 0 ? profile.payMethods : ALL_PAYS,
    [profile]
  );
  const configuredPayKey = configuredPays.join(",");

  const [stores, setStores] = useState<Store[]>([]);
  const [sort, setSort] = useState<"distance" | "discount">("distance");
  const [view, setView] = useState<"map" | "list">("map");
  const [center, setCenter] = useState(DEFAULT_CENTER);
  const [selected, setSelected] = useState<Store | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [onlyMyCards, setOnlyMyCards] = useState(true);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [activeCat, setActiveCat] = useState<StoreCategory | null>(null);
  const [activePays, setActivePays] = useState<PayMethod[]>(configuredPays);

  useEffect(() => {
    fetchOptions()
      .then((options) => setCategories(options.categories))
      .catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    setActivePays(configuredPays);
  }, [configuredPayKey]);

  const myCardIds = useMemo(
    () => (profile?.cardIds ?? []).slice().sort((a, b) => a - b),
    [profile]
  );
  const cardFilter = onlyMyCards && myCardIds.length > 0 ? myCardIds : undefined;
  const cardFilterKey = cardFilter?.join(",") ?? "";
  const payKey = activePays.slice().sort().join(",");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setApiError(null);
    setSelected(null);

    fetchNearbyStores({
      lat: center.lat,
      lng: center.lng,
      radius_m: 3000,
      pay: activePays.length === ALL_PAYS.length ? undefined : activePays,
      card_ids: cardFilter,
      category: activeCat ? [activeCat] : undefined,
      sort,
    })
      .then((data) => {
        if (!cancelled) setStores(data);
      })
      .catch((error: Error) => {
        if (!cancelled) setApiError(error.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [center, payKey, sort, cardFilterKey, activeCat]);

  useEffect(() => {
    if (!ready || view !== "map" || !mapRef.current) return;
    const kakao = window.kakao;
    if (mapObj.current && mapEl.current === mapRef.current) return;

    mapObj.current = new kakao.maps.Map(mapRef.current, {
      center: new kakao.maps.LatLng(center.lat, center.lng),
      level: 4,
    });
    mapEl.current = mapRef.current;
    mapObj.current.addControl(
      new kakao.maps.ZoomControl(),
      kakao.maps.ControlPosition.RIGHT
    );
    overlays.current = [];
  }, [ready, view]);

  useEffect(() => {
    if (!ready || view !== "map" || !mapObj.current) return;
    const kakao = window.kakao;
    overlays.current.forEach((overlay) => overlay.setMap(null));
    overlays.current = [];

    stores.forEach((store) => {
      const rate = topRate(store);
      const meta = CATEGORY_META[store.category];
      const button = document.createElement("button");
      button.type = "button";
      button.className = `store-icon${selected?.id === store.id ? " is-selected" : ""}`;
      button.setAttribute(
        "aria-label",
        `${store.brand} ${store.branch}, ${rate > 0 ? `최대 ${rate}% 할인` : "혜택 확인"}`
      );

      const marker = document.createElement("span");
      marker.className = "discount-marker";
      marker.style.setProperty("--category-color", meta.color);

      const dot = document.createElement("span");
      dot.className = "category-spot";
      const label = document.createElement("strong");
      label.textContent = `${rate > 0 ? `${rate}%` : "혜택"} · ${store.brand}`;
      marker.append(dot, label);
      button.append(marker);

      button.addEventListener("click", (event) => {
        event.stopPropagation();
        setSelected(store);
      });

      const overlay = new kakao.maps.CustomOverlay({
        map: mapObj.current,
        position: new kakao.maps.LatLng(store.lat, store.lng),
        content: button,
        yAnchor: 1.1,
        zIndex: selected?.id === store.id ? 8 : 3,
      });
      overlays.current.push(overlay);
    });
  }, [ready, stores, view, selected]);

  function togglePay(method: PayMethod) {
    setActivePays((current) => {
      if (!current.includes(method)) return [...current, method];
      if (current.length === 1) return current;
      return current.filter((item) => item !== method);
    });
  }

  function setMapCenter(next: { lat: number; lng: number }, level = 4) {
    setCenter(next);
    if (mapObj.current && ready) {
      mapObj.current.setCenter(new window.kakao.maps.LatLng(next.lat, next.lng));
      mapObj.current.setLevel(level);
    }
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setApiError("이 브라우저는 위치 조회를 지원하지 않아요.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setMapCenter({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        });
      },
      () => setApiError("위치 권한이 거부되어 기본 위치를 표시합니다.")
    );
  }

  function renderDeals(store: Store) {
    return (
      <div className="deal-details">
        {store.best_deal && (
          <div className={`best-deal ${store.best_deal.kind}`}>
            <span className="tag">BEST</span>
            <strong>{store.best_deal.label}</strong>
            <span className="rate">{store.best_deal.discount_rate}%</span>
            {store.best_deal.note && <small>{store.best_deal.note}</small>}
          </div>
        )}

        {store.offers.length > 0 && (
          <div className="deal-group">
            <p className="deal-title">간편결제</p>
            {store.offers.map((offer) => (
              <div key={offer.pay_method} className="offer-row">
                <span className={`pay-badge ${offer.pay_method}`}>
                  {PAY_LABELS[offer.pay_method]}
                </span>
                <strong>{offer.discount_rate}%</strong>
                <small>{offer.condition_text}</small>
              </div>
            ))}
          </div>
        )}

        {store.card_benefits.length > 0 && (
          <div className="deal-group">
            <p className="deal-title">카드 할인</p>
            {store.card_benefits.map((benefit) => (
              <div key={benefit.id} className="offer-row card-row">
                <span className="card-name">{benefit.card_name}</span>
                <strong>{benefitLabel(benefit)}</strong>
                {benefit.confidence !== "confirmed" && (
                  <span className="warn-badge">확인 필요</span>
                )}
                {benefit.excludes_simple_pay && (
                  <span className="excl-badge">간편결제 제외</span>
                )}
                {benefit.conditions.length > 0 && (
                  <small>{benefit.conditions.join(" · ")}</small>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="map-page page-shell">
      <section className="hero map-hero" aria-labelledby="map-page-title">
        <nav className="page-steps compact" aria-label="서비스 단계">
          <span className="page-step"><b>1</b> 카드·수단 선택</span>
          <span className="page-step is-active"><b>2</b> 할인 지도</span>
        </nav>
        <p className="eyebrow">PERSONAL BENEFIT MAP</p>
        <h1 id="map-page-title">
          내 수단으로 가장 유리한<br />
          <strong>할인</strong>을 한눈에.
        </h1>
        <div className="hero-meta">
          <p className="location-status">
            경희대 · 회기역 · 외대앞의 결제 혜택을 비교해 드려요.
          </p>
          <button className="location-button" type="button" onClick={useMyLocation}>
            ◎ 내 위치 찾기
          </button>
        </div>
      </section>

      <section className="filters" aria-labelledby="category-filter-title">
        <div className="section-heading">
          <h2 id="category-filter-title">업종</h2>
          <span className="filter-summary">{activeCat ? CATEGORY_META[activeCat].label : "전체 업종"}</span>
        </div>
        <div className="pay-filters" role="group" aria-label="업종 필터">
          <button
            type="button"
            className="pay-filter"
            aria-pressed={activeCat === null}
            onClick={() => setActiveCat(null)}
          >
            전체
          </button>
          {categories
            .filter((category) => category.value !== "other")
            .map((category) => (
              <button
                key={category.value}
                type="button"
                className="pay-filter category-filter"
                style={{ "--category-color": CATEGORY_META[category.value].color } as CSSProperties}
                aria-pressed={activeCat === category.value}
                onClick={() => setActiveCat(category.value)}
              >
                <span className="category-dot" />
                {category.label}
              </button>
            ))}
        </div>
      </section>

      <section className="filters" aria-labelledby="method-filter-title">
        <div className="section-heading">
          <h2 id="method-filter-title">내 결제수단</h2>
          <button
            className="text-button"
            type="button"
            onClick={() => setActivePays(configuredPays)}
          >
            전체 켜기
          </button>
        </div>
        <div className="pay-filters" role="group" aria-label="결제수단 필터">
          {configuredPays.map((method) => (
            <button
              key={method}
              type="button"
              className={`pay-filter method-filter ${method}`}
              aria-pressed={activePays.includes(method)}
              onClick={() => togglePay(method)}
            >
              {PAY_LABELS[method]}
            </button>
          ))}
          <button
            type="button"
            className="pay-filter method-filter card-method"
            aria-pressed={onlyMyCards && myCardIds.length > 0}
            disabled={myCardIds.length === 0}
            onClick={() => setOnlyMyCards((value) => !value)}
          >
            내 카드 {myCardIds.length}개
          </button>
        </div>
      </section>

      <section className="results" aria-labelledby="result-title">
        <div className="section-heading results-heading">
          <div>
            <p className="eyebrow">NEARBY BENEFITS</p>
            <h2 id="result-title">주변 혜택 <span>{stores.length}</span></h2>
          </div>
          <div className="result-actions">
            <div className="view-toggle" role="group" aria-label="보기 방식">
              <button
                type="button"
                aria-pressed={view === "map"}
                onClick={() => setView("map")}
              >
                지도
              </button>
              <button
                type="button"
                aria-pressed={view === "list"}
                onClick={() => setView("list")}
              >
                리스트
              </button>
            </div>
            <label className="sort-label">
              정렬
              <select
                value={sort}
                onChange={(event) =>
                  setSort(event.target.value as "distance" | "discount")
                }
              >
                <option value="distance">가까운 순</option>
                <option value="discount">할인 높은 순</option>
              </select>
            </label>
          </div>
        </div>

        {sdkError && <p className="notice error">{sdkError}</p>}
        {apiError && <p className="notice error">{apiError}</p>}
        {loading && <p className="loading-note">혜택을 불러오는 중…</p>}

        {view === "map" ? (
          <div className="map-view">
            <div className="map-search">경희대 · 회기역 · 외대앞 할인 지도</div>
            <button
              className="map-recenter"
              type="button"
              onClick={() => setMapCenter(DEFAULT_CENTER)}
            >
              전체 보기
            </button>
            <div className="category-legend" aria-label="업종 색상 안내">
              {(["restaurant", "cafe", "convenience"] as StoreCategory[]).map((category) => (
                <span
                  key={category}
                  style={{ "--category-color": CATEGORY_META[category].color } as CSSProperties}
                >
                  {CATEGORY_META[category].label}
                </span>
              ))}
            </div>
            <div ref={mapRef} className="map-canvas" aria-label="주변 할인 지도" />
            {selected && (
              <aside
                className="map-store-card"
                style={{ "--category-color": CATEGORY_META[selected.category].color } as CSSProperties}
                aria-live="polite"
              >
                <button
                  className="close"
                  type="button"
                  onClick={() => setSelected(null)}
                  aria-label="매장 상세 닫기"
                >
                  ×
                </button>
                <p className="map-popup-brand">{CATEGORY_META[selected.category].label}</p>
                <h3>{selected.brand} {selected.branch}</h3>
                <p className="address">{selected.address}</p>
                {renderDeals(selected)}
              </aside>
            )}
          </div>
        ) : (
          <div className="benefit-list">
            {stores.length === 0 && !loading && (
              <div className="empty-state">
                <p>선택한 조건으로 받을 수 있는 혜택이 없어요.</p>
                <button className="primary-button" type="button" onClick={() => setActiveCat(null)}>
                  전체 업종 보기
                </button>
              </div>
            )}
            {stores.map((store) => (
              <article
                key={store.id}
                className="benefit-card"
                style={{ "--category-color": CATEGORY_META[store.category].color } as CSSProperties}
              >
                <div className="store-logo">
                  <span>{CATEGORY_META[store.category].icon}</span>
                </div>
                <div className="card-content">
                  <div className="card-topline">
                    <span className="store-name">
                      <span className="category-dot" />
                      {store.brand} {store.branch}
                    </span>
                    <span className="distance">{formatDistance(store.distance_m)}</span>
                  </div>
                  <p className="address">{store.address}</p>
                  {renderDeals(store)}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <p className="page-notice">
        카드 혜택은 2026-08 기준 수집 데이터이며, 실제 적용 조건은 카드사 공지를 확인해 주세요.
      </p>
    </div>
  );
}
