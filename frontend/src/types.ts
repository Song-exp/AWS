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
  user_id: string | null;
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
