import type {
  ChatRequest,
  ChatResponse,
  LocalBenefitParams,
  LocalBenefitsPage,
  MetaOptions,
  MyPageData,
  NearbyParams,
  AuthUser,
  BoardCategory,
  CommunityBoard,
  PostDetail,
  PostPage,
  PostSummary,
  SavingSummary,
  SpendPayload,
  Store,
  ToggleResult,
} from "./types";

// 개발: vite 프록시(/api -> :8000). 배포: VITE_API_BASE로 오버라이드.
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

// 인증은 HttpOnly 세션 쿠키로 한다. fetch는 기본적으로 쿠키를 싣지 않으므로
// 모든 요청에 명시해야 한다. 빠뜨리면 로그인해도 401이 난다.
const CREDS: RequestInit = { credentials: "include" };

export async function sendMessage(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat/message`, {
    ...CREDS,
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
  const res = await fetch(`${API_BASE}/meta/options`, CREDS);
  if (!res.ok) {
    throw new Error(`옵션 조회 실패: ${res.status}`);
  }
  return (await res.json()) as MetaOptions;
}

/** 대화 중 과거 신청서(PDF 등)를 첨부한다. */
export async function uploadChatFile(
  file: File,
  sessionId: string | null
): Promise<ChatResponse> {
  const form = new FormData();
  form.append("file", file);
  if (sessionId) form.append("session_id", sessionId);

  const res = await fetch(`${API_BASE}/chat/upload`, {
    ...CREDS,
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

  const res = await fetch(`${API_BASE}/stores/nearby?${q.toString()}`, CREDS);
  if (!res.ok) {
    throw new Error(`매장 조회 실패: ${res.status}`);
  }
  return (await res.json()) as Store[];
}

export async function fetchMyPage(cardIds: number[]): Promise<MyPageData> {
  const q = new URLSearchParams();
  cardIds.forEach((id) => q.append("card_ids", String(id)));
  const res = await fetch(`${API_BASE}/me/summary?${q.toString()}`, CREDS);
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
  const res = await fetch(`${API_BASE}/stores/local-benefits?${q.toString()}`, CREDS);
  if (!res.ok) {
    throw new Error(`제휴·지역화폐 조회 실패: ${res.status}`);
  }
  return (await res.json()) as LocalBenefitsPage;
}


/** 세이빙 대시보드 조회(월간 누적 절감액 · 전환율 · 보상 환산). */
export async function fetchSavingsSummary(): Promise<SavingSummary> {
  const res = await fetch(`${API_BASE}/savings/summary`, CREDS);
  if (!res.ok) {
    throw new Error(`세이빙 조회 실패: ${res.status}`);
  }
  return (await res.json()) as SavingSummary;
}

/** '소비 완료' 토글. 절감액이 월간 누적에 반영된다. */
export async function recordSpend(payload: SpendPayload): Promise<void> {
  const res = await fetch(`${API_BASE}/savings/spend`, {
    ...CREDS,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = `기록 실패: ${res.status}`;
    try {
      const j = await res.json();
      if (j.detail) detail = j.detail;
    } catch {
      // JSON이 아니면 기본 메시지
    }
    throw new Error(detail);
  }
}

/** 매장 혜택 조회 기록(전환율 KPI의 분모). 실패해도 UI를 막지 않는다. */
export async function recordStoreView(
  storeId: number | null,
  storeLabel: string
): Promise<void> {
  try {
    await fetch(`${API_BASE}/savings/view`, {
      ...CREDS,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ store_id: storeId, store_label: storeLabel }),
    });
  } catch {
    // 분석용 이벤트라 실패해도 사용자 흐름을 끊지 않는다.
  }
}


// ===== 인증 =====
async function authRequest(path: string, body: unknown): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...CREDS,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const j = await res.json();
    if (typeof j.detail === "string") return j.detail;
  } catch {
    // JSON이 아니면 기본 메시지
  }
  return fallback;
}

/** 세션 복원. 로그인 상태가 아니면 null(에러가 아니다). */
export async function fetchCurrentUser(): Promise<AuthUser | null> {
  const res = await fetch(`${API_BASE}/auth/me`, CREDS);
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`세션 확인 실패: ${res.status}`);
  return (await res.json()) as AuthUser;
}

export async function signup(
  email: string,
  password: string,
  claimUserId?: string | null
): Promise<AuthUser> {
  const res = await authRequest("/auth/signup", {
    email,
    password,
    // 로그인 도입 전 이 브라우저에 쌓인 데이터를 새 계정으로 승계한다.
    claim_user_id: claimUserId ?? null,
  });
  if (!res.ok) throw new Error(await readError(res, "가입에 실패했습니다."));
  return (await res.json()) as AuthUser;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const res = await authRequest("/auth/login", { email, password });
  if (!res.ok) throw new Error(await readError(res, "로그인에 실패했습니다."));
  return (await res.json()) as AuthUser;
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, { ...CREDS, method: "POST" });
}


// ===== 계정 설정 =====
/** 프로필 부분 수정. 보낸 필드만 바뀐다(안 보낸 값은 유지). */
export async function updateProfile(
  patch: Partial<{
    nickname: string | null;
    gender: string | null;
    telecom: string | null;
    card_ids: number[];
    preferred_pay_methods: string[];
    student_credentials: string[];
    benefit_programs: string[];
    income_bracket: number | null;
    gpa: number | null;
  }>
): Promise<AuthUser> {
  const res = await fetch(`${API_BASE}/auth/profile`, {
    ...CREDS,
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(await readError(res, "프로필 저장에 실패했습니다."));
  return (await res.json()) as AuthUser;
}

export async function changePassword(
  currentPassword: string,
  newPassword: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/password`, {
    ...CREDS,
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  if (!res.ok) throw new Error(await readError(res, "비밀번호 변경에 실패했습니다."));
}

/** 모든 기기에서 로그아웃. */
export async function logoutEverywhere(): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/sessions`, { ...CREDS, method: "DELETE" });
  if (!res.ok) throw new Error(await readError(res, "로그아웃에 실패했습니다."));
}

/** 회원 탈퇴. 계정과 개인 데이터가 실제로 삭제된다. */
export async function deleteAccount(password: string): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/delete`, {
    ...CREDS,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) throw new Error(await readError(res, "탈퇴에 실패했습니다."));
}


/** 재설정 링크 요청. 가입 여부와 무관하게 성공한다(계정 존재를 흘리지 않음). */
export async function requestPasswordReset(email: string): Promise<void> {
  const res = await authRequest("/auth/password/forgot", { email });
  if (!res.ok) throw new Error(await readError(res, "요청에 실패했습니다."));
}

/** 메일로 받은 토큰으로 새 비밀번호 설정. 성공 후에는 다시 로그인해야 한다. */
export async function resetPassword(
  token: string,
  newPassword: string
): Promise<void> {
  const res = await authRequest("/auth/password/reset", {
    token,
    new_password: newPassword,
  });
  if (!res.ok) throw new Error(await readError(res, "재설정에 실패했습니다."));
}

// ===== 커뮤니티 =====
async function getJson<T>(path: string, errorLabel: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, CREDS);
  if (!res.ok) throw new Error(await readError(res, `${errorLabel}: ${res.status}`));
  return (await res.json()) as T;
}

export async function fetchBoards(
  category?: BoardCategory | null,
  q?: string
): Promise<CommunityBoard[]> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (q) params.set("q", q);
  const suffix = params.toString() ? `?${params}` : "";
  return getJson<CommunityBoard[]>(`/community/boards${suffix}`, "게시판 조회 실패");
}

export async function fetchBoardPosts(
  slug: string,
  offset = 0,
  limit = 20
): Promise<PostPage> {
  return getJson<PostPage>(
    `/community/boards/${slug}/posts?offset=${offset}&limit=${limit}`,
    "글 목록 조회 실패"
  );
}

export async function fetchBoardQuestions(slug: string): Promise<PostSummary[]> {
  return getJson<PostSummary[]>(
    `/community/boards/${slug}/questions`,
    "질문글 조회 실패"
  );
}

/** HOT/BEST/내 글/댓글 단 글/스크랩 — 모두 같은 페이지 형태다. */
export async function fetchPostFeed(
  feed: "hot" | "best" | "me/posts" | "me/commented" | "me/scraps",
  offset = 0,
  limit = 20
): Promise<PostPage> {
  return getJson<PostPage>(
    `/community/${feed}?offset=${offset}&limit=${limit}`,
    "목록 조회 실패"
  );
}

export async function fetchPost(postId: number): Promise<PostDetail> {
  return getJson<PostDetail>(`/community/posts/${postId}`, "글 조회 실패");
}

export async function createPost(input: {
  board_slug: string;
  title: string;
  body: string;
  is_anonymous: boolean;
  is_question: boolean;
}): Promise<PostDetail> {
  const res = await authRequest("/community/posts", input);
  if (!res.ok) throw new Error(await readError(res, "글 등록에 실패했습니다."));
  return (await res.json()) as PostDetail;
}

export async function createComment(
  postId: number,
  body: string,
  isAnonymous: boolean,
  parentId?: number | null
): Promise<PostDetail> {
  const res = await authRequest(`/community/posts/${postId}/comments`, {
    body,
    is_anonymous: isAnonymous,
    parent_id: parentId ?? null,
  });
  if (!res.ok) throw new Error(await readError(res, "댓글 등록에 실패했습니다."));
  return (await res.json()) as PostDetail;
}

async function postToggle(path: string): Promise<ToggleResult> {
  const res = await fetch(`${API_BASE}${path}`, { ...CREDS, method: "POST" });
  if (!res.ok) throw new Error(await readError(res, "요청에 실패했습니다."));
  return (await res.json()) as ToggleResult;
}

export const togglePostLike = (id: number) =>
  postToggle(`/community/posts/${id}/like`);
export const toggleCommentLike = (id: number) =>
  postToggle(`/community/comments/${id}/like`);
export const togglePostScrap = (id: number) =>
  postToggle(`/community/posts/${id}/scrap`);

export async function deletePost(postId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/community/posts/${postId}`, {
    ...CREDS,
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await readError(res, "삭제에 실패했습니다."));
}

export async function deleteComment(commentId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/community/comments/${commentId}`, {
    ...CREDS,
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await readError(res, "삭제에 실패했습니다."));
}

export async function reportPost(postId: number, reason: string): Promise<void> {
  const res = await authRequest(`/community/posts/${postId}/report`, { reason });
  if (!res.ok) throw new Error(await readError(res, "신고에 실패했습니다."));
}
