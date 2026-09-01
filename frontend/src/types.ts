// ===== 챗봇 =====
export interface Candidate {
  index: number;
  id: number;
  title: string;
  deadline?: string | null;
  reasons: string[];
}

export interface DraftAnswer {
  question: string;
  draft_text: string;
  sources: string[];
}

export interface Draft {
  scholarship_id: number;
  answers: DraftAnswer[];
  used_history: boolean;
}

export interface ChatResponse {
  session_id: string;
  state: string;
  message: string;
  candidates: Candidate[];
  draft: Draft | null;
  profile?: Record<string, unknown>;
}

export interface ChatRequest {
  session_id: string | null;
  message: string;
}

// ===== 지도(TMI) =====
export type PayMethod = "kakao" | "toss" | "naver";
export type StudentCredential = "student_card" | "student_tok";
export type BenefitProgram = "khu_alliance" | "onnuri" | "seoulpay" | "zeropay";

export type StoreCategory =
  | "convenience"
  | "cafe"
  | "restaurant"
  | "mart"
  | "bakery"
  | "hnb"
  | "other";

export interface Offer {
  pay_method: PayMethod;
  discount_rate: number;
  condition_text: string | null;
}

export type BenefitType =
  | "percent"
  | "amount"
  | "cashback"
  | "event"
  | "unverified"
  | "expired";

export interface CardBenefit {
  id: number;
  card_name: string;
  issuer: string | null;
  benefit_type: BenefitType;
  value_min: number | null;
  value_max: number | null;
  benefit_text: string | null;
  min_payment_krw: number | null;
  min_payment_raw: string | null;
  cap_text: string | null;
  period_text: string | null;
  conditions: string[];
  excludes_simple_pay: boolean;
  confidence: "confirmed" | "conditional" | "unverified";
  source_url: string | null;
}

export interface BestDeal {
  kind: "simple_pay" | "card";
  label: string;
  discount_rate: number;
  note: string | null;
}

export interface Store {
  id: number;
  brand: string;
  branch: string;
  category: StoreCategory;
  address: string | null;
  lat: number;
  lng: number;
  mark: string | null;
  color: string | null;
  offers: Offer[];
  card_benefits: CardBenefit[];
  distance_m: number | null;
  max_discount_rate: number;
  max_card_discount_rate: number;
  best_deal: BestDeal | null;
  local_benefits?: LocalBenefit[];
}

export interface LocalBenefit {
  id: number;
  source_key: string;
  merchant_name: string;
  category: StoreCategory;
  category_label: string | null;
  address: string | null;
  search_query: string;
  lat: number | null;
  lng: number | null;
  source_type: string;
  programs: BenefitProgram[];
  credentials: StudentCredential[];
  requires: string | null;
  benefit_text: string;
  discount_type: string | null;
  discount_value: number | null;
  min_spend: number | null;
  max_amount: number | null;
  conditions: string | null;
  valid_to: string | null;
  confidence: string | null;
  source_url: string | null;
}

export interface LocalBenefitsPage {
  items: LocalBenefit[];
  total: number;
  offset: number;
  limit: number;
}

export interface LocalBenefitParams {
  programs?: BenefitProgram[];
  credentials?: StudentCredential[];
  category?: StoreCategory[];
  q?: string;
  offset?: number;
  limit?: number;
}

export interface NearbyParams {
  lat?: number;
  lng?: number;
  radius_m?: number;
  pay?: PayMethod[];
  card_ids?: number[];
  category?: StoreCategory[];
  sort?: "distance" | "discount";
}

// ===== 온보딩 =====
export interface CardOption {
  id: number;
  card_name: string;
  issuer: string | null;
  benefit_count: number;
}

export interface PayOption {
  value: PayMethod;
  label: string;
}

export interface CategoryOption {
  value: StoreCategory;
  label: string;
}

export interface ProfileOption {
  value: string;
  label: string;
}

export interface MetaOptions {
  cards: CardOption[];
  pay_methods: PayOption[];
  categories: CategoryOption[];
  telecoms: string[];
  telecom_supported: boolean;
  student_credentials: ProfileOption[];
  benefit_programs: ProfileOption[];
}

/** 온보딩에서 수집하는 성별(localStorage 저장) */
export type Gender = "male" | "female";

/** 온보딩 사용자(나)와 시연용 3명을 포함한 페르소나 식별자 */
export type PersonaId = "me" | "demo_a" | "demo_b" | "demo_c";

/** 페르소나마다 전환되는 혜택 설정 */
export interface ProfileSettings {
  gender: Gender | null;
  cardIds: number[];
  telecom: string | null;
  payMethods: PayMethod[];
  studentCredentials: StudentCredential[];
  benefitPrograms: BenefitProgram[];
}

/** 온보딩에서 수집하는 내 정보(localStorage 저장) */
export interface UserProfileLocal extends ProfileSettings {
  userId: string;
  personaId: PersonaId;
  /** 데모 페르소나를 보다가 '나'로 돌아올 때 복원할 실제 사용자 설정 */
  personalProfile: ProfileSettings;
}

// ===== 마이페이지 =====
export interface MyDocument {
  id: number;
  doc_type: string;
  prompt_question: string | null;
  content_text: string;
  char_count: number;
  created_at: string | null;
}

export interface MyApplication {
  id: string;
  scholarship_name: string;
  organization: string | null;
  source: string;
  result: string;
  tags: string[];
  is_reusable: boolean;
  created_at: string | null;
  documents: MyDocument[];
}

export interface MyCard {
  id: number;
  card_name: string;
  issuer: string | null;
}

export interface MyPageData {
  user_id: string;
  applications: MyApplication[];
  documents: MyDocument[];
  cards: MyCard[];
  counts: Record<string, number>;
}

/** 세이빙 대시보드(기획서 3.3) */
export interface SavingRecord {
  id: number;
  kind: string;
  store_label: string;
  original_amount: number;
  final_amount: number;
  saved_amount: number;
  method_label: string;
  created_at: string | null;
}

export interface SavingReward {
  label: string;
  count: number;
  message: string;
}

export interface SavingSummary {
  user_id: string;
  month: string;
  month_saved: number;
  total_saved: number;
  month_count: number;
  viewed_count: number;
  /** 소비완료 / 혜택조회. KPI 목표 0.25 */
  conversion_rate: number;
  reward: SavingReward | null;
  recent: SavingRecord[];
}

export interface SpendPayload {
  user_id: string;
  store_id?: number | null;
  store_label?: string;
  original_amount: number;
  final_amount: number;
  method_label?: string;
}

/** 로그인한 사용자(서버 세션 기준). userId의 출처는 이제 서버다. */
export interface AuthUser {
  id: string;
  email: string | null;
  nickname: string | null;
  income_bracket: number | null;
  gpa: number | null;
  grade_level: string | null;
  region: string | null;
  major: string | null;
  interests: string[];
  preferred_pay_methods: string[];
  gender: string | null;
  telecom: string | null;
  card_ids: number[];
  student_credentials: string[];
  benefit_programs: string[];
}

// ===== 커뮤니티 =====
export type BoardCategory = "general" | "career" | "promo" | "group";

export interface CommunityBoard {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  category: BoardCategory;
  allows_anonymous: boolean;
  forces_anonymous: boolean;
  /** 마지막으로 읽은 뒤 새 글이 있는지 — 목록의 N 뱃지 */
  has_new: boolean;
}

export interface PostSummary {
  id: number;
  board_id: number;
  board_name: string;
  title: string;
  preview: string;
  author_label: string;
  is_question: boolean;
  like_count: number;
  comment_count: number;
  created_at: string | null;
  is_mine: boolean;
}

export interface PostComment {
  id: number;
  parent_id: number | null;
  body: string;
  author_label: string;
  like_count: number;
  liked_by_me: boolean;
  is_mine: boolean;
  is_deleted: boolean;
  created_at: string | null;
}

export interface PostDetail {
  id: number;
  board_id: number;
  board_name: string;
  title: string;
  body: string;
  author_label: string;
  is_question: boolean;
  like_count: number;
  comment_count: number;
  view_count: number;
  liked_by_me: boolean;
  scrapped_by_me: boolean;
  is_mine: boolean;
  created_at: string | null;
  comments: PostComment[];
}

export interface PostPage {
  items: PostSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface ToggleResult {
  active: boolean;
  count: number;
}
