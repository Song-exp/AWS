import type {
  ChatRequest,
  ChatResponse,
  LocalBenefitParams,
  LocalBenefitsPage,
  MetaOptions,
  MyPageData,
  NearbyParams,
  Store,
} from "./types";

// 개발: vite 프록시(/api -> :8000). 배포: VITE_API_BASE로 오버라이드.
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export async function sendMessage(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`요청 실패: ${res.status}`);
  }
  return (await res.json()) as ChatResponse;
}

export async function fetchOptions(): Promise<MetaOptions> {
  const res = await fetch(`${API_BASE}/meta/options`);
  if (!res.ok) {
    throw new Error(`옵션 조회 실패: ${res.status}`);
  }
  return (await res.json()) as MetaOptions;
}

/** 대화 중 과거 신청서(PDF 등)를 첨부한다. */
export async function uploadChatFile(
  file: File,
  sessionId: string | null,
  userId: string | null
): Promise<ChatResponse> {
  const form = new FormData();
  form.append("file", file);
  if (sessionId) form.append("session_id", sessionId);
  if (userId) form.append("user_id", userId);

  const res = await fetch(`${API_BASE}/chat/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    let detail = `업로드 실패: ${res.status}`;
    try {
      const j = await res.json();
      if (j.detail) detail = j.detail;
    } catch {
      // 응답이 JSON이 아니면 기본 메시지 사용
    }
    throw new Error(detail);
  }
  return (await res.json()) as ChatResponse;
}

export async function fetchNearbyStores(params: NearbyParams): Promise<Store[]> {
  const q = new URLSearchParams();
  if (params.lat !== undefined) q.set("lat", String(params.lat));
  if (params.lng !== undefined) q.set("lng", String(params.lng));
  if (params.radius_m !== undefined) q.set("radius_m", String(params.radius_m));
  if (params.sort) q.set("sort", params.sort);
  // 복수 파라미터
  params.pay?.forEach((p) => q.append("pay", p));
  params.card_ids?.forEach((id) => q.append("card_ids", String(id)));
  params.category?.forEach((cat) => q.append("category", cat));

  const res = await fetch(`${API_BASE}/stores/nearby?${q.toString()}`);
  if (!res.ok) {
    throw new Error(`매장 조회 실패: ${res.status}`);
  }
  return (await res.json()) as Store[];
}

export async function fetchMyPage(
  userId: string,
  cardIds: number[]
): Promise<MyPageData> {
  const q = new URLSearchParams();
  q.set("user_id", userId);
  cardIds.forEach((id) => q.append("card_ids", String(id)));
  const res = await fetch(`${API_BASE}/me/summary?${q.toString()}`);
  if (!res.ok) {
    throw new Error(`마이페이지 조회 실패: ${res.status}`);
  }
  return (await res.json()) as MyPageData;
}


export async function fetchLocalBenefits(
  params: LocalBenefitParams
): Promise<LocalBenefitsPage> {
  const q = new URLSearchParams();
  params.programs?.forEach((value) => q.append("program", value));
  params.credentials?.forEach((value) => q.append("credential", value));
  params.category?.forEach((value) => q.append("category", value));
  if (params.q) q.set("q", params.q);
  if (params.offset !== undefined) q.set("offset", String(params.offset));
  if (params.limit !== undefined) q.set("limit", String(params.limit));
  const res = await fetch(`${API_BASE}/stores/local-benefits?${q.toString()}`);
  if (!res.ok) {
    throw new Error(`제휴·지역화폐 조회 실패: ${res.status}`);
  }
  return (await res.json()) as LocalBenefitsPage;
}
