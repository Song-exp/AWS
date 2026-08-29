import { useEffect, useMemo, useRef, useState } from "react";
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

// 서비스 영역(경희대·한국외대 일대) 기본 중심
const DEFAULT_CENTER = { lat: 37.5938, lng: 127.0564 };

function logoFor(brand: string): string | null {
  if (brand === "GS25") return "/logo-gs25.png";
  if (brand === "세븐일레븐") return "/logo-seven.png";
  if (brand.startsWith("이마트24")) return "/logo-emart24.png";
  return null; // CU는 텍스트 배지
}

function formatDistance(m: number | null): string {
  if (m === null) return "";
  if (m < 1000) return `${Math.max(10, Math.round(m / 10) * 10)}m`;
  return `${(m / 1000).toFixed(1)}km`;
}

/** 지도 마커에 띄울 대표 할인율(간편결제/카드 중 큰 값). */
function topRate(s: Store): number {
  return Math.max(s.max_discount_rate, s.max_card_discount_rate);
}

/** 카드 혜택 표시 문구. 정률/정액/이벤트를 구분해 보여준다. */
function benefitLabel(b: CardBenefit): string {
  if (b.benefit_text) return b.benefit_text;
  if (b.benefit_type === "percent" && b.value_min !== null) {
    return b.value_max && b.value_max !== b.value_min
      ? `${b.value_min}~${b.value_max}%`
      : `${b.value_min}%`;
  }
  if (b.benefit_type === "amount" && b.value_min !== null) {
    return `${b.value_min.toLocaleString()}원 할인`;
  }
  return "행사 진행";
}

interface Props {
  /** 온보딩에서 고른 내 정보. 없으면 전체를 보여준다. */
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

  const [stores, setStores] = useState<Store[]>([]);
  const [sort, setSort] = useState<"distance" | "discount">("distance");
  const [view, setView] = useState<"map" | "list">("map");
  const [center, setCenter] = useState(DEFAULT_CENTER);
  const [selected, setSelected] = useState<Store | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  // 내 카드만 볼지 여부(온보딩에서 카드를 골랐을 때만 의미 있음)
  const [onlyMyCards, setOnlyMyCards] = useState(true);
  // 카테고리 필터(빈 배열 = 전체)
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [activeCats, setActiveCats] = useState<StoreCategory[]>([]);

  // 카테고리 옵션 로드
  useEffect(() => {
    fetchOptions()
      .then((o) => setCategories(o.categories))
      .catch(() => setCategories([]));
  }, []);

  const catKey = activeCats.join(",");

  // 결제수단은 온보딩에서 받은 값을 그대로 사용한다(지도에서 다시 묻지 않음)
  const payList = useMemo<PayMethod[]>(
    () =>
      profile && profile.payMethods.length > 0 ? profile.payMethods : ALL_PAYS,
    [profile]
  );
  const payKey = payList.join(",");

  const myCardIds = useMemo(
    () => (profile?.cardIds ?? []).slice().sort((a, b) => a - b),
    [profile]
  );
  const cardFilter = onlyMyCards && myCardIds.length > 0 ? myCardIds : undefined;
  const cardFilterKey = cardFilter ? cardFilter.join(",") : "";

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setApiError(null);
    fetchNearbyStores({
      lat: center.lat,
      lng: center.lng,
      radius_m: 3000,
      pay: payList.length === ALL_PAYS.length ? undefined : payList,
      card_ids: cardFilter,
      category: activeCats.length > 0 ? activeCats : undefined,
      sort,
    })
      .then((data) => {
        if (!cancelled) setStores(data);
      })
      .catch((e: Error) => {
        if (!cancelled) setApiError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [center, payKey, sort, cardFilterKey, catKey]);

  // 지도 초기화. 뷰 토글로 컨테이너가 교체되면 다시 생성한다.
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

  // 마커 갱신: 할인율을 지도 위에 배지로 표시
  useEffect(() => {
    if (!ready || view !== "map" || !mapObj.current) return;
    const kakao = window.kakao;
    overlays.current.forEach((o) => o.setMap(null));
    overlays.current = [];

    stores.forEach((s) => {
      const rate = topRate(s);
      const isCardBest = s.best_deal?.kind === "card";
      const el = document.createElement("button");
      el.type = "button";
      el.className = `store-marker-btn${isCardBest ? " card-best" : ""}`;
      el.setAttribute("aria-label", `${s.brand} ${s.branch} 최대 ${rate}% 할인`);
      const logo = logoFor(s.brand);
      el.innerHTML = `
        <span class="marker-rate">${rate > 0 ? `${rate}%` : "-"}</span>
        <span class="marker-badge" style="border-color:${s.color ?? "#888"}">
          ${logo ? `<img src="${logo}" alt="" />` : `<b>${s.mark ?? ""}</b>`}
        </span>
        <span class="marker-label">${s.branch}</span>`;
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        setSelected(s);
      });
      const overlay = new kakao.maps.CustomOverlay({
        map: mapObj.current,
        position: new kakao.maps.LatLng(s.lat, s.lng),
        content: el,
        yAnchor: 0.5,
        zIndex: 3,
      });
      overlays.current.push(overlay);
    });
  }, [ready, stores, view]);

  function toggleCat(cat: StoreCategory) {
    setActiveCats((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setApiError("이 브라우저는 위치 조회를 지원하지 않아요.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const next = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setCenter(next);
        if (mapObj.current) {
          mapObj.current.setCenter(
            new window.kakao.maps.LatLng(next.lat, next.lng)
          );
        }
      },
      () => setApiError("위치 권한이 거부되었어요. 기본 위치로 표시합니다.")
    );
  }

  /** 간편결제 vs 카드 비교 블록 */
  function renderDeals(s: Store) {
    return (
      <>
        {s.best_deal && (
          <div className={`best-deal ${s.best_deal.kind}`}>
            <span className="tag">최적</span>
            <strong>{s.best_deal.label}</strong>
            <span className="rate">{s.best_deal.discount_rate}%</span>
            {s.best_deal.note && <small>{s.best_deal.note}</small>}
          </div>
        )}

        <div className="deal-group">
          <p className="deal-title">간편결제</p>
          {s.offers.map((o) => (
            <div key={o.pay_method} className="offer-row">
              <span className={`pay-badge ${o.pay_method}`}>
                {PAY_LABELS[o.pay_method]}
              </span>
              <strong>{o.discount_rate}%</strong>
              <small>{o.condition_text}</small>
            </div>
          ))}
        </div>

        {s.card_benefits.length > 0 && (
          <div className="deal-group">
            <p className="deal-title">카드 할인</p>
            {s.card_benefits.map((b) => (
              <div key={b.id} className="offer-row card-row">
                <span className="card-name">{b.card_name}</span>
                <strong>{benefitLabel(b)}</strong>
                {b.confidence !== "confirmed" && (
                  <span className="warn-badge">확인필요</span>
                )}
                {b.excludes_simple_pay && (
                  <span className="excl-badge">간편결제 불가</span>
                )}
                {b.conditions.length > 0 && <small>{b.conditions.join(" · ")}</small>}
                {b.min_payment_krw && (
                  <small>최소 {b.min_payment_krw.toLocaleString()}원</small>
                )}
              </div>
            ))}
          </div>
        )}
      </>
    );
  }

  return (
    <div className="map-page">
      <section className="hero">
        <p className="eyebrow">오늘 어디서 결제할까요?</p>
        <h1>
          가까운 편의점의 <strong>결제 할인</strong>을 한눈에.
        </h1>
        <button className="location-button" type="button" onClick={useMyLocation}>
          ⌖ 내 위치 찾기
        </button>
      </section>

      {categories.length > 0 && (
        <section className="category-bar" aria-label="매장 카테고리 필터">
          <button
            type="button"
            className={`cat-chip ${activeCats.length === 0 ? "on" : ""}`}
            onClick={() => setActiveCats([])}
          >
            전체
          </button>
          {categories
            .filter((c) => c.value !== "other")
            .map((c) => (
              <button
                key={c.value}
                type="button"
                className={`cat-chip ${activeCats.includes(c.value) ? "on" : ""}`}
                aria-pressed={activeCats.includes(c.value)}
                onClick={() => toggleCat(c.value)}
              >
                {c.label}
              </button>
            ))}
        </section>
      )}

      <section className="results">
        <div className="section-heading">
          <h2>
            주변 혜택 <span className="count">{stores.length}</span>
          </h2>
          <div className="result-actions">
            <div className="view-toggle" role="group" aria-label="보기 방식">
              <button
                type="button"
                className={view === "map" ? "on" : ""}
                aria-pressed={view === "map"}
                onClick={() => setView("map")}
              >
                지도
              </button>
              <button
                type="button"
                className={view === "list" ? "on" : ""}
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
                onChange={(e) =>
                  setSort(e.target.value as "distance" | "discount")
                }
              >
                <option value="distance">가까운 순</option>
                <option value="discount">할인 높은 순</option>
              </select>
            </label>
          </div>
        </div>

        {myCardIds.length > 0 && (
          <label className="mycard-toggle">
            <input
              type="checkbox"
              checked={onlyMyCards}
              onChange={(e) => setOnlyMyCards(e.target.checked)}
            />
            내 보유 카드({myCardIds.length}개) 혜택만 보기
          </label>
        )}

        {sdkError && <p className="notice error">{sdkError}</p>}
        {apiError && <p className="notice error">{apiError}</p>}
        {loading && <p className="notice">불러오는 중…</p>}

        {view === "map" ? (
          <div className="map-view">
            <div
              ref={mapRef}
              className="map-canvas"
              aria-label="주변 편의점 할인 지도"
            />
            {selected && (
              <aside className="map-store-card" aria-live="polite">
                <button
                  className="close"
                  type="button"
                  onClick={() => setSelected(null)}
                  aria-label="닫기"
                >
                  ×
                </button>
                <p className="brand">{selected.brand}</p>
                <h3>{selected.branch}</h3>
                <p className="address">{selected.address}</p>
                {renderDeals(selected)}
              </aside>
            )}
          </div>
        ) : (
          <div className="benefit-list">
            {stores.length === 0 && !loading && (
              <div className="empty-state">
                <p>조건에 맞는 혜택이 없어요.</p>
              </div>
            )}
            {stores.map((s) => (
              <article key={s.id} className="benefit-card">
                <div
                  className="store-logo"
                  style={{ borderColor: s.color ?? "#888" }}
                >
                  {logoFor(s.brand) ? (
                    <img src={logoFor(s.brand)!} alt="" />
                  ) : (
                    <b>{s.mark}</b>
                  )}
                </div>
                <div className="card-content">
                  <div className="card-topline">
                    <span className="store-name">
                      {s.brand} {s.branch}
                    </span>
                    <span className="distance">
                      {formatDistance(s.distance_m)}
                    </span>
                  </div>
                  <p className="address">{s.address}</p>
                  {renderDeals(s)}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <p className="notice">
        카드 혜택은 2026-08 기준 수집 데이터예요. 조건·기간은 카드사 공지를 확인해
        주세요.
      </p>
    </div>
  );
}
