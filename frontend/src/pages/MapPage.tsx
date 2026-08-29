import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { fetchLocalBenefits, fetchNearbyStores, fetchOptions } from "../api";
import { DEMO_PERSONAS, getPersonaForProfile } from "../personas";
import type {
  BenefitProgram,
  CardBenefit,
  CategoryOption,
  LocalBenefit,
  PayMethod,
  StudentCredential,
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
const PROGRAM_LABELS: Record<BenefitProgram, string> = {
  khu_alliance: "경희대 제휴",
  onnuri: "온누리",
  seoulpay: "서울Pay+",
  zeropay: "제로페이",
};
const PROGRAM_COLORS: Record<BenefitProgram, string> = {
  khu_alliance: "#A40F16",
  onnuri: "#C0A353",
  seoulpay: "#AD1D19",
  zeropay: "#987B32",
};
const CREDENTIAL_LABELS: Record<StudentCredential, string> = {
  student_card: "학생증",
  student_tok: "톡학생증",
};
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

function distanceMeters(
  a: { lat: number; lng: number },
  b: { lat: number; lng: number }
): number {
  const radius = 6371000;
  const toRad = (value: number) => (value * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * radius * Math.asin(Math.sqrt(h));
}

function localBenefitRate(benefit: LocalBenefit): number {
  return benefit.discount_type === "percent" && benefit.discount_value
    ? benefit.discount_value
    : 0;
}

function isCashDiscount(benefit: LocalBenefit): boolean {
  const text = [benefit.requires, benefit.conditions, benefit.benefit_text]
    .filter(Boolean)
    .join(" ");
  return text.includes("현금") || text.includes("계좌이체");
}

function localBenefitMarkerLabel(benefit: LocalBenefit): string {
  if (isCashDiscount(benefit)) return "현금 할인";
  if (benefit.discount_type === "percent" && benefit.discount_value) {
    return `${benefit.discount_value}%`;
  }
  if (benefit.discount_type === "fixed" && (benefit.discount_value ?? 0) > 0) {
    return "정액 할인";
  }
  if (benefit.discount_type === "fixed") return "제휴가";
  if (benefit.discount_type === "event") return "제휴 혜택";
  if (benefit.discount_type === "currency") return "가맹";
  return "혜택";
}

function localBenefitValueLabel(benefit: LocalBenefit): string {
  const value = benefit.discount_value ?? 0;
  if (isCashDiscount(benefit)) {
    const amount =
      benefit.discount_type === "percent" && value > 0
        ? ` · ${value}%`
        : benefit.discount_type === "fixed" && value > 0
          ? ` · ${value.toLocaleString("ko-KR")}원`
          : "";
    return `현금 할인${amount}`;
  }
  if (benefit.discount_type === "percent" && value > 0) return `${value}% 할인`;
  if (benefit.discount_type === "fixed" && value > 0) {
    return `${value.toLocaleString("ko-KR")}원 정액 할인`;
  }
  if (benefit.discount_type === "fixed") return "학생 제휴가";
  if (benefit.discount_type === "event") return "제휴 혜택";
  if (benefit.discount_type === "currency") return "사용 가능 가맹점";
  return "혜택 확인";
}

function localBenefitHasSaving(benefit: LocalBenefit): boolean {
  return (
    isCashDiscount(benefit) ||
    (benefit.discount_type === "percent" && (benefit.discount_value ?? 0) > 0) ||
    (benefit.discount_type === "fixed" && (benefit.discount_value ?? 0) > 0)
  );
}

function primaryProgram(benefit: LocalBenefit): BenefitProgram {
  return benefit.programs[0] ?? "khu_alliance";
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
  const persona = profile ? getPersonaForProfile(profile) : DEMO_PERSONAS[0];

  const configuredPays = useMemo<PayMethod[]>(
    () =>
      profile && profile.payMethods.length > 0 ? profile.payMethods : ALL_PAYS,
    [profile]
  );
  const configuredPayKey = configuredPays.join(",");

  const [stores, setStores] = useState<Store[]>([]);
  const [localBenefits, setLocalBenefits] = useState<LocalBenefit[]>([]);
  const [localStores, setLocalStores] = useState<Store[]>([]);
  const [localBenefitTotal, setLocalBenefitTotal] = useState(0);
  const [localLoading, setLocalLoading] = useState(false);
  const [sort, setSort] = useState<"distance" | "discount">("distance");
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

  useEffect(() => {
    setActiveCat(persona.preferredCategories[0] ?? null);
    setOnlyMyCards(true);
  }, [persona.id]);

  const myCardIds = useMemo(
    () => (profile?.cardIds ?? []).slice().sort((a, b) => a - b),
    [profile]
  );
  const cardFilter = onlyMyCards
    ? myCardIds.length > 0
      ? myCardIds
      : [0]
    : undefined;
  const cardFilterKey = cardFilter?.join(",") ?? "";
  const payKey = activePays.slice().sort().join(",");
  const benefitPrograms = profile?.benefitPrograms ?? [];
  const studentCredentials = profile?.studentCredentials ?? [];
  const benefitProgramKey = benefitPrograms.slice().sort().join(",");
  const credentialKey = studentCredentials.slice().sort().join(",");
  const visibleStores = useMemo(
    () => [...stores, ...localStores],
    [stores, localStores]
  );
  const recommendedStore = useMemo(
    () =>
      visibleStores.reduce<Store | null>((best, store) => {
        if (!best || topRate(store) > topRate(best)) return store;
        return best;
      }, null),
    [visibleStores]
  );

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
    let cancelled = false;
    if (benefitPrograms.length === 0) {
      setLocalBenefits([]);
      setLocalStores([]);
      setLocalBenefitTotal(0);
      return;
    }
    setLocalLoading(true);
    setLocalStores([]);
    fetchLocalBenefits({
      programs: benefitPrograms,
      credentials: studentCredentials,
      category: activeCat ? [activeCat] : undefined,
      limit: 60,
    })
      .then((page) => {
        if (cancelled) return;
        setLocalBenefits(page.items);
        setLocalBenefitTotal(page.total);
      })
      .catch((error: Error) => {
        if (!cancelled) setApiError(error.message);
      })
      .finally(() => {
        if (!cancelled) setLocalLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [benefitProgramKey, credentialKey, activeCat]);

  useEffect(() => {
    if (!ready || !window.kakao?.maps?.services || localBenefits.length === 0) {
      if (localBenefits.length === 0) setLocalStores([]);
      return;
    }
    let cancelled = false;
    const kakao = window.kakao;
    const geocoder = new kakao.maps.services.Geocoder();
    const places = new kakao.maps.services.Places();

    const geocode = (benefit: LocalBenefit) =>
      new Promise<{ lat: number; lng: number } | null>((resolve) => {
        if (benefit.lat !== null && benefit.lng !== null) {
          resolve({ lat: benefit.lat, lng: benefit.lng });
          return;
        }
        const cacheKey = `tmi.geocode.v1.${benefit.source_key}`;
        try {
          const cached = sessionStorage.getItem(cacheKey);
          if (cached) {
            resolve(JSON.parse(cached));
            return;
          }
        } catch {
          // 저장소를 사용할 수 없어도 검색은 계속한다.
        }
        const finish = (result: any[] | null, status: string) => {
          if (status === kakao.maps.services.Status.OK && result?.[0]) {
            const point = { lat: Number(result[0].y), lng: Number(result[0].x) };
            try {
              sessionStorage.setItem(cacheKey, JSON.stringify(point));
            } catch {
              // 캐시 실패는 지도 표시를 막지 않는다.
            }
            resolve(point);
          } else {
            resolve(null);
          }
        };
        const keyword = () => places.keywordSearch(benefit.search_query, finish);
        if (benefit.address) {
          geocoder.addressSearch(benefit.address, (result: any[], status: string) => {
            if (status === kakao.maps.services.Status.OK && result?.[0]) {
              finish(result, status);
            } else {
              keyword();
            }
          });
        } else {
          keyword();
        }
      });

    const resolveInBatches = async () => {
      const resolved: Array<{
        benefit: LocalBenefit;
        point: { lat: number; lng: number } | null;
      }> = [];
      for (let index = 0; index < localBenefits.length; index += 8) {
        if (cancelled) break;
        const batch = await Promise.all(
          localBenefits.slice(index, index + 8).map(async (benefit) => ({
            benefit,
            point: await geocode(benefit),
          }))
        );
        resolved.push(...batch);
      }
      return resolved;
    };

    resolveInBatches().then((resolved) => {
      if (cancelled) return;
      const mapped = resolved.flatMap(({ benefit, point }) => {
        if (!point) return [];
        const distance = distanceMeters(center, point);
        if (distance > 5000) return [];
        const program = primaryProgram(benefit);
        const rate = localBenefitRate(benefit);
        const store: Store = {
          id: -benefit.id,
          brand: benefit.merchant_name,
          branch: benefit.programs.map((item) => PROGRAM_LABELS[item]).join(" · "),
          category: benefit.category,
          address: benefit.address,
          lat: point.lat,
          lng: point.lng,
          mark: PROGRAM_LABELS[program].slice(0, 1),
          color: PROGRAM_COLORS[program],
          offers: [],
          card_benefits: [],
          distance_m: Math.round(distance * 10) / 10,
          max_discount_rate: rate,
          max_card_discount_rate: 0,
          best_deal: null,
          local_benefits: [benefit],
        };
        return [store];
      });
      mapped.sort(
        sort === "discount"
          ? (a, b) => topRate(b) - topRate(a)
          : (a, b) => (a.distance_m ?? 0) - (b.distance_m ?? 0)
      );
      setLocalStores(mapped);
    });
    return () => {
      cancelled = true;
    };
  }, [ready, localBenefits, center, sort]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
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
  }, [ready]);

  useEffect(() => {
    if (!ready || !mapObj.current) return;
    const kakao = window.kakao;
    overlays.current.forEach((overlay) => overlay.setMap(null));
    overlays.current = [];

    visibleStores.forEach((store) => {
      const rate = topRate(store);
      const meta = CATEGORY_META[store.category];
      const localBenefit = store.local_benefits?.[0];
      const markerColor = localBenefit ? store.color ?? meta.color : meta.color;
      const button = document.createElement("button");
      button.type = "button";
      button.className = `store-icon${selected?.id === store.id ? " is-selected" : ""}`;
      button.setAttribute(
        "aria-label",
        `${store.brand} ${store.branch}, ${
          localBenefit
            ? localBenefitValueLabel(localBenefit)
            : rate > 0
              ? `최대 ${rate}% 할인`
              : "혜택 확인"
        }`
      );

      const marker = document.createElement("span");
      const hasSaving = localBenefit
        ? localBenefitHasSaving(localBenefit)
        : rate > 0;
      marker.className = `discount-marker${hasSaving ? " has-saving" : ""}`;
      marker.style.setProperty("--category-color", markerColor);

      const dot = document.createElement("span");
      dot.className = "category-spot";
      const place = document.createElement("span");
      place.className = "marker-place";
      const categoryLabel = document.createElement("small");
      categoryLabel.textContent = localBenefit
        ? localBenefit.programs.map((item) => PROGRAM_LABELS[item]).join(" · ")
        : meta.label;
      const storeLabel = document.createElement("b");
      storeLabel.textContent = `${store.brand} ${store.branch}`;
      place.append(categoryLabel, storeLabel);
      const saving = document.createElement("strong");
      saving.textContent = localBenefit
        ? localBenefitMarkerLabel(localBenefit)
        : rate > 0
          ? `${rate}%`
          : "혜택";
      marker.append(dot, place, saving);
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
  }, [ready, visibleStores, selected]);

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
        {store.local_benefits?.map((benefit) => (
          <div key={benefit.source_key} className="local-benefit-deal">
            <div className="local-benefit-programs">
              {benefit.programs.map((program) => (
                <span
                  key={program}
                  style={{ "--program-color": PROGRAM_COLORS[program] } as CSSProperties}
                >
                  {PROGRAM_LABELS[program]}
                </span>
              ))}
            </div>
            <div className="local-benefit-title">
              <strong>{benefit.benefit_text}</strong>
              <span className={`local-benefit-value${isCashDiscount(benefit) ? " is-cash" : ""}`}>
                {localBenefitValueLabel(benefit)}
              </span>
            </div>
            {benefit.requires && <p>이용 조건 · {benefit.requires}</p>}
            {benefit.conditions && <small>{benefit.conditions}</small>}
            {benefit.valid_to && <small>유효기간 · {benefit.valid_to}</small>}
            {benefit.source_url && (
              <a href={benefit.source_url} target="_blank" rel="noreferrer">
                혜택 근거 보기
              </a>
            )}
          </div>
        ))}
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
            개인정보와 보유수단에 맞춰 주변 혜택 순위를 즉시 비교해 드려요.
          </p>
          <button className="location-button" type="button" onClick={useMyLocation}>
            ◎ 내 위치 찾기
          </button>
        </div>
      </section>

      <section className="filters" aria-labelledby="method-filter-title">
        <div className="personal-recommendation" aria-live="polite">
          <span>{persona.name} 맞춤 추천</span>
          <strong>
            {recommendedStore
              ? `${recommendedStore.brand} ${recommendedStore.branch} · 최대 ${topRate(recommendedStore)}%`
              : "선택한 조건의 혜택을 찾고 있어요"}
          </strong>
          <p>
            {persona.cardLabel} · {persona.preferredCategories.map((category) => CATEGORY_META[category].label).join(" · ")} 중심으로 비교한 결과예요.
          </p>
        </div>
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
        <div className="profile-benefit-strip" aria-label="학생 인증과 제휴 지역화폐 연결 상태">
          <div className="profile-benefit-strip-head">
            <strong>학생·지역 혜택</strong>
            <span>가맹점 데이터 {localBenefitTotal.toLocaleString("ko-KR")}개 연결</span>
          </div>
          <div className="profile-benefit-chips">
            {studentCredentials.map((credential) => (
              <span key={credential} className="credential-chip">
                {CREDENTIAL_LABELS[credential]}
              </span>
            ))}
            {benefitPrograms.map((program) => (
              <span
                key={program}
                className="program-chip"
                style={{ "--program-color": PROGRAM_COLORS[program] } as CSSProperties}
              >
                {PROGRAM_LABELS[program]}
              </span>
            ))}
            {studentCredentials.length === 0 && benefitPrograms.length === 0 && (
              <span className="profile-benefit-empty">내 정보 수정에서 혜택 수단을 선택해 주세요.</span>
            )}
          </div>
        </div>
      </section>

      <section className="results" aria-labelledby="result-title">
        <div className="section-heading results-heading">
          <div>
            <p className="eyebrow">NEARBY BENEFITS</p>
            <h2 id="result-title">주변 혜택 <span>{visibleStores.length}</span></h2>
          </div>
          <div className="result-actions">
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
        {(loading || localLoading) && <p className="loading-note">혜택을 불러오는 중…</p>}

        <div className="map-view">
          <div className="map-search">경희대 · 회기역 · 외대앞 <strong>맞춤 혜택</strong> 지도</div>
          <button
            className="map-recenter"
            type="button"
            onClick={() => setMapCenter(DEFAULT_CENTER)}
          >
            전체 보기
          </button>
          <div className="map-category-panel">
            <div className="map-category-head">
              <strong>어디로 갈까요?</strong>
              <button
                className="text-button"
                type="button"
                disabled={myCardIds.length === 0}
                onClick={() => setOnlyMyCards((value) => !value)}
              >
                내 수단 {activePays.length + myCardIds.length}개
              </button>
            </div>
            <div className="map-category-filters" role="group" aria-label="업종 필터">
              <button
                type="button"
                className="map-category-button"
                style={{ "--category-color": "#A40F16" } as CSSProperties}
                aria-pressed={activeCat === null}
                onClick={() => setActiveCat(null)}
              >
                <span aria-hidden="true">◎</span>
                전체
              </button>
              {categories
                .filter((category) => category.value !== "other")
                .map((category) => (
                  <button
                    key={category.value}
                    type="button"
                    className={`map-category-button${persona.preferredCategories.includes(category.value) ? " is-preferred" : ""}`}
                    style={{ "--category-color": CATEGORY_META[category.value].color } as CSSProperties}
                    aria-pressed={activeCat === category.value}
                    onClick={() => setActiveCat(category.value)}
                  >
                    <span aria-hidden="true">{CATEGORY_META[category.value].icon}</span>
                    {category.label}
                  </button>
                ))}
            </div>
          </div>
          <div ref={mapRef} className="map-canvas" aria-label="주변 할인 지도" />
          {selected && (
            <aside
              className="map-store-card"
              style={{
                "--category-color": selected.local_benefits?.[0]
                  ? selected.color ?? CATEGORY_META[selected.category].color
                  : CATEGORY_META[selected.category].color,
              } as CSSProperties}
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
              <p className="map-popup-brand">
                {selected.local_benefits?.[0]
                  ? selected.local_benefits[0].programs
                      .map((program) => PROGRAM_LABELS[program])
                      .join(" · ")
                  : CATEGORY_META[selected.category].label}
              </p>
              <h3>
                {selected.brand}
                {!selected.local_benefits?.[0] && ` ${selected.branch}`}
              </h3>
              <p className="address">{selected.address ?? "장소검색으로 위치 확인"}</p>
              {renderDeals(selected)}
            </aside>
          )}
        </div>
      </section>

      <p className="page-notice">
        카드 혜택은 2026-08 기준이며, 학생제휴·온누리·서울Pay+·제로페이 가맹점은 제공된 원본 주소를 지도검색으로 표시합니다. 실제 적용 조건은 각 운영기관 공지를 확인해 주세요.
      </p>
    </div>
  );
}
