import type {
  BenefitProgram,
  Gender,
  PayMethod,
  PersonaId,
  StoreCategory,
  StudentCredential,
  UserProfileLocal,
} from "./types";

export type DemoPersonaId = Exclude<PersonaId, "me">;

export interface PersonaView {
  id: PersonaId;
  name: string;
  archetype: string;
  gender: Gender;
  cardLabel: string;
  cardIds: number[];
  payMethods: PayMethod[];
  telecom: string | null;
  preferredCategories: StoreCategory[];
  studentCredentials: StudentCredential[];
  benefitPrograms: BenefitProgram[];
  savingsAmount: number;
  scholarshipAmount: number;
}

export interface DemoPersona extends PersonaView {
  id: DemoPersonaId;
  telecom: string;
}

export const DEMO_PERSONAS: DemoPersona[] = [
  {
    id: "demo_a",
    name: "민지",
    archetype: "카페·문화형",
    gender: "female",
    cardLabel: "KB 펭수 노리 카드",
    cardIds: [2],
    payMethods: ["kakao", "naver"],
    telecom: "SKT",
    preferredCategories: ["cafe", "convenience", "bakery"],
    studentCredentials: ["student_tok"],
    benefitPrograms: ["khu_alliance"],
    savingsAmount: 184_500,
    scholarshipAmount: 3_500_000,
  },
  {
    id: "demo_b",
    name: "준호",
    archetype: "학교생활형",
    gender: "male",
    cardLabel: "하나 네이버페이머니",
    cardIds: [3],
    payMethods: ["naver"],
    telecom: "KT",
    preferredCategories: ["restaurant", "mart", "convenience"],
    studentCredentials: ["student_card"],
    benefitPrograms: ["khu_alliance", "seoulpay"],
    savingsAmount: 271_800,
    scholarshipAmount: 5_000_000,
  },
  {
    id: "demo_c",
    name: "서연",
    archetype: "생활절약형",
    gender: "female",
    cardLabel: "올리브영 현대카드 Plus (지도 카드 연동 예정)",
    cardIds: [],
    payMethods: ["toss"],
    telecom: "LG U+",
    preferredCategories: ["hnb", "convenience", "restaurant"],
    studentCredentials: ["student_card"],
    benefitPrograms: ["onnuri", "seoulpay", "zeropay"],
    savingsAmount: 392_400,
    scholarshipAmount: 4_200_000,
  },
];

export function isPersonaId(value: unknown): value is PersonaId {
  return value === "me" || isDemoPersonaId(value);
}

export function isDemoPersonaId(value: unknown): value is DemoPersonaId {
  return value === "demo_a" || value === "demo_b" || value === "demo_c";
}

export function getPersona(personaId: PersonaId): DemoPersona {
  return DEMO_PERSONAS.find((persona) => persona.id === personaId) ?? DEMO_PERSONAS[0];
}

/** 현재 활성 프로필을 지도·마이페이지에 표시할 페르소나 정보로 변환한다. */
export function getPersonaForProfile(profile: UserProfileLocal): PersonaView {
  if (profile.personaId !== "me") return getPersona(profile.personaId);

  const cardLabel = profile.cardIds.length > 0
    ? `내 카드 ${profile.cardIds.length}개`
    : "선택 카드 없음";
  return {
    id: "me",
    name: "나",
    archetype: "직접 설정",
    gender: profile.gender ?? "female",
    cardLabel,
    cardIds: profile.cardIds,
    payMethods: profile.payMethods,
    telecom: profile.telecom,
    preferredCategories: ["cafe", "restaurant", "convenience"],
    studentCredentials: profile.studentCredentials,
    benefitPrograms: profile.benefitPrograms,
    savingsAmount: 0,
    scholarshipAmount: 0,
  };
}
