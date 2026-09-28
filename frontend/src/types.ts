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

/** 지출 분야. 매장 업종(StoreCategory)과 다른 축이다.
 *  업종은 '지도에 찍히는 가게가 무엇인가', 이쪽은 '돈이 어디로 나가는가'. */
export type SpendCategory =
  | "food"
  | "transport"
  | "culture"
  | "study"
  | "living"
  | "fixed"
  | "finance";

export const SPEND_LABELS: Record<SpendCategory, string> = {
  food: "식비",
  transport: "교통",
  culture: "문화·여가",
  study: "학업",
  living: "생활·쇼핑",
  fixed: "고정비",
  finance: "금융·수입",
};
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
  id: number;
  /** '이미 끝난 혜택이에요' 제보 수 */
  report_count: number;
  /** 임계를 넘겨 추천에서 빠졌는가 */
  reported: boolean;
  pay_method: PayMethod;
  discount_rate: number;
  condition_text: string | null;
  /** 실제 프로모션을 확인하지 않은 예시 값 */
  is_sample: boolean;
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
  category: SpendCategory | null;
  category_label: string | null;
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
  tier: SavingTier | null;
  by_category: CategorySaving[];
  recent: SavingRecord[];
}

/** 절감액 등급. 금액은 싣지 않는다 — 버킷만 내려온다. */
export interface SavingTier {
  index: number;
  label: string;
  next_label: string | null;
  next_at: number | null;
  demoted: boolean;
}

export interface CategorySaving {
  category: SpendCategory | null;
  label: string;
  saved: number;
  count: number;
}

export interface SpendPayload {
  user_id: string;
  store_id?: number | null;
  store_label?: string;
  category?: SpendCategory | null;
  original_amount: number;
  final_amount: number;
  method_label?: string;
}

/** 로그인한 사용자(서버 세션 기준). userId의 출처는 이제 서버다. */
export interface AuthUser {
  id: string;
  email: string | null;
  /** 인증 메일의 링크를 눌러 주소가 확인됐는가 */
  email_verified: boolean;
  /** 마감 알림 메일 수신 동의 */
  reminder_enabled: boolean;
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
  /** 별명 글에만 실린다. 익명 글은 null */
  author_tier: string | null;
  category: SpendCategory | null;
  category_label: string | null;
  is_question: boolean;
  like_count: number;
  comment_count: number;
  created_at: string | null;
  is_mine: boolean;
  /** 첫 첨부 이미지 경로(API_BASE 기준). 없으면 null */
  thumbnail_url: string | null;
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
  /** 별명 글에만 실린다. 익명 글은 null */
  author_tier: string | null;
  category: SpendCategory | null;
  category_label: string | null;
  is_question: boolean;
  like_count: number;
  comment_count: number;
  view_count: number;
  liked_by_me: boolean;
  scrapped_by_me: boolean;
  is_mine: boolean;
  created_at: string | null;
  /** 첨부 이미지 경로들(API_BASE 기준) */
  image_urls: string[];
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

// ---------------- 혜택 탭 ----------------
export type PostingStatus =
  | "open"
  | "closing_soon"
  | "closed"
  | "schedule_changed"
  | "needs_review";

export interface Posting {
  id: number;
  title: string;
  organization: string | null;
  category: "scholarship" | "gov_benefit";
  source_platform: string;
  source_url: string;
  deadline_at: string | null;
  posted_at: string | null;
  status: PostingStatus;
  benefit: Record<string, unknown>;
  days_left: number | null;
}

export interface PostingDetail extends Posting {
  eligibility: Record<string, unknown>;
  required_documents: string[];
  body_text: string;
}

export interface PostingPage {
  items: Posting[];
  total: number;
  offset: number;
  limit: number;
}

/** 상시 혜택. 마감이 없고 한 번 켜면 끝난다. */
export interface BenefitItem {
  key: string;
  title: string;
  category: SpendCategory;
  category_label: string;
  summary: string;
  /** 연 절감액 **추정치**. 요율은 수시로 바뀐다. */
  saving_hint_krw: number;
  effort_min: number;
  credential: string | null;
  url: string | null;
  search_hint: string | null;
  done: boolean;
}

export interface BenefitItemsPage {
  items: BenefitItem[];
  remaining_hint_krw: number;
  remaining_count: number;
}

export interface OfferReportResult {
  active: boolean;
  count: number;
  flagged: boolean;
}

/** 커뮤니티 피드(게시판이 아닌 묶음 목록). BoardListPage 를 지우면서 옮겨 왔다. */
export type FeedKey = "me/posts" | "me/commented" | "me/scraps" | "hot" | "best";
