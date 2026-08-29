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

// ===== 지도(페이픽) =====
export type PayMethod = "kakao" | "toss" | "naver";

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

export interface MetaOptions {
  cards: CardOption[];
  pay_methods: PayOption[];
  categories: CategoryOption[];
  telecoms: string[];
  telecom_supported: boolean;
}

/** 온보딩에서 수집하는 내 정보(localStorage 저장) */
export interface UserProfileLocal {
  userId: string;
  cardIds: number[];
  telecom: string | null;
  payMethods: PayMethod[];
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
