// ═══════════════════════════════════════════════════════════
// TMI + 거지앱 통합 데이터 (2026-08 기준 MVP 예시)
// 범위: 경희대 ~ 회기역 ~ 외대앞 일대
// ═══════════════════════════════════════════════════════════

// ─── 결제수단 후보군 (온보딩에서 선택) ───
const PAYMENT_GROUPS = [
  {
    category: 'student_id',
    label: '제휴·학생 인증',
    emoji: '',
    methods: [
      { id: 'khu_alliance', name: '경희대 제휴', issuer: '경희대' },
      { id: 'student_tok', name: '카카오톡 톡학생증', issuer: '카카오톡' },
      { id: 'student_card', name: '실물 학생증', issuer: '경희대' },
    ],
  },
  {
    category: 'telecom',
    label: '통신사',
    emoji: '',
    methods: [
      { id: 'telecom_skt', name: 'T멤버십', issuer: 'SKT' },
      { id: 'telecom_kt', name: 'KT멤버십', issuer: 'KT' },
      { id: 'telecom_lgu', name: 'U+멤버십', issuer: 'LG U+' },
    ],
  },
  {
    category: 'pay',
    label: '페이',
    emoji: '',
    methods: [
      { id: 'pay_kakao', name: '카카오페이', issuer: '카카오' },
      { id: 'pay_naver', name: '네이버페이', issuer: '네이버' },
      { id: 'pay_toss', name: '토스페이', issuer: '토스' },
    ],
  },
  {
    category: 'card',
    label: '카드',
    emoji: '',
    methods: [
      { id: 'kb_narasarang', name: '나라사랑카드', issuer: 'KB' },
      { id: 'kb_pengsoo', name: '펭수 노리 카드', issuer: 'KB' },
      { id: 'hana_naverpay', name: '네이버페이머니', issuer: '하나' },
      { id: 'hana_narasarang', name: '나라사랑카드', issuer: '하나' },
      { id: 'ibk_easy_cashback', name: 'EASY Cashback', issuer: '기업' },
      { id: 'hyundai_oliveyoung_plus', name: '올리브영 현대카드 Plus', issuer: '현대' },
    ],
  },
  {
    category: 'local_currency',
    label: '지역화폐',
    emoji: '',
    methods: [
      { id: 'local_seoul', name: '동대문구사랑상품권', issuer: '동대문구' },
      { id: 'local_onnuri', name: '온누리상품권', issuer: '소상공인시장진흥공단' },
    ],
  },
]

// 발표 시연용 가상 사용자. 보유수단과 소비 성향을 함께 바꿔
// 사용자 전환 시 추천 매장과 순위가 즉시 달라지는 것을 보여준다.
const DEMO_USERS = [
  {
    id: 'demo_a',
    name: '민지 · 카페·문화형',
    gender: 'female',
    savingsAmount: 184500,
    scholarshipAmount: 3500000,
    cardLabel: 'KB 펭수 노리 카드',
    owned: ['khu_alliance', 'student_tok', 'telecom_skt', 'pay_kakao', 'pay_naver', 'kb_pengsoo'],
    preferences: ['cafe', 'culture', 'convenience'],
    profile: { naverPlus: true, kakaoPlus: true, telecomGrade: 'vip', gradeLabel: 'VIP' },
  },
  {
    id: 'demo_b',
    name: '준호 · 학교생활형',
    gender: 'male',
    savingsAmount: 271800,
    scholarshipAmount: 5000000,
    cardLabel: '하나 네이버페이머니',
    owned: ['khu_alliance', 'student_card', 'telecom_kt', 'pay_naver', 'hana_naverpay', 'local_seoul'],
    preferences: ['campus', 'restaurant', 'lifestyle'],
    profile: { naverPlus: true, kakaoPlus: false, telecomGrade: 'normal', gradeLabel: 'Silver' },
  },
  {
    id: 'demo_c',
    name: '서연 · 생활절약형',
    gender: 'female',
    savingsAmount: 392400,
    scholarshipAmount: 4200000,
    cardLabel: '올리브영 현대카드 Plus',
    owned: ['student_card', 'telecom_lgu', 'pay_toss', 'hyundai_oliveyoung_plus', 'local_seoul', 'local_onnuri'],
    preferences: ['lifestyle', 'convenience', 'restaurant'],
    profile: { naverPlus: false, kakaoPlus: false, telecomGrade: 'vip', gradeLabel: 'Gold' },
  },
]

// id → 결제수단 객체 빠른 조회용
const PAYMENT_METHODS = {}
PAYMENT_GROUPS.forEach(g => {
  g.methods.forEach(m => {
    PAYMENT_METHODS[m.id] = { ...m, category: g.category, categoryLabel: g.label, emoji: g.emoji }
  })
})

const CATEGORY_LABELS = {
  student_id: '제휴·학생 인증',
  telecom: '통신사',
  pay: '페이',
  card: '카드',
  local_currency: '지역화폐',
}

// ─── 매장 데이터 (편의점 + 카페 + 음식점) ───
// storeCategory: 'convenience' | 'cafe' | 'restaurant'
const STORES = [
  // ═══ 편의점 (TMI 기존 데이터) ═══
  { id: 's_cu_khu', brand: 'CU', branch: '경희대점', category: 'convenience', mark: 'CU', color: '#7b2cbf', address: '경희대로4길 15', lat: 37.592493, lng: 127.053511 },
  { id: 's_gs_khumed', brand: 'GS25', branch: '경희의대점', category: 'convenience', mark: 'GS', color: '#0879c9', address: '회기로23가길 21', lat: 37.592324, lng: 127.054227 },
  { id: 's_seven_dorm', brand: '세븐일레븐', branch: '경희대기숙사점', category: 'convenience', mark: '7', color: '#e31e24', address: '이문로9길 46', lat: 37.594255, lng: 127.056536 },
  { id: 's_gs_front', brand: 'GS25', branch: '경희정문점', category: 'convenience', mark: 'GS', color: '#0879c9', address: '경희대로 정문 앞', lat: 37.5926702, lng: 127.0524544 },
  { id: 's_gs_imun', brand: 'GS25', branch: '이문회기점', category: 'convenience', mark: 'GS', color: '#0879c9', address: '회기로25길 54', lat: 37.592105, lng: 127.056759 },
  { id: 's_cu_kaist', brand: 'CU', branch: '카이스트점', category: 'convenience', mark: 'CU', color: '#7b2cbf', address: '회기로 119', lat: 37.591598, lng: 127.049904 },
  { id: 's_gs_kaist', brand: 'GS25', branch: '카이스트원룸점', category: 'convenience', mark: 'GS', color: '#0879c9', address: '회기로 118', lat: 37.591332, lng: 127.049674 },
  { id: 's_gs_oneroom', brand: 'GS25', branch: '경희원룸점', category: 'convenience', mark: 'GS', color: '#0879c9', address: '이문로3길 66', lat: 37.590936, lng: 127.051562 },
  { id: 's_seven_daehyun', brand: '세븐일레븐', branch: '경희대대현점', category: 'convenience', mark: '7', color: '#e31e24', address: '회기로 163', lat: 37.590871, lng: 127.054273 },
  { id: 's_cu_hoegijung', brand: 'CU', branch: '회기중앙점', category: 'convenience', mark: 'CU', color: '#7b2cbf', address: '회기로29길 9', lat: 37.590577, lng: 127.05791 },
  { id: 's_gs_cheongryang', brand: 'GS25', branch: '청량현대점', category: 'convenience', mark: 'GS', color: '#0879c9', address: '이문로1길 21', lat: 37.590168, lng: 127.051564 },
  { id: 's_seven_happypark', brand: '세븐일레븐', branch: '회기해피파크점', category: 'convenience', mark: '7', color: '#e31e24', address: '이문로 19', lat: 37.589825, lng: 127.05517 },
  { id: 's_cu_namu', brand: 'CU', branch: '회기나무점', category: 'convenience', mark: 'CU', color: '#7b2cbf', address: '이문로 18', lat: 37.589273, lng: 127.055308 },
  { id: 's_emart_jll', brand: '이마트24', branch: 'JLL회기로점', category: 'convenience', mark: '24', color: '#f5c400', address: '회기로29길 34', lat: 37.591682, lng: 127.0582606 },

  // ═══ 카페 ═══
  { id: 's_cafe_starbucks', brand: '스타벅스', branch: '회기역점', category: 'cafe', mark: '★', color: '#00704a', address: '회기로 188', lat: 37.5894, lng: 127.0562 },
  { id: 's_cafe_twosome', brand: '투썸플레이스', branch: '회기역점', category: 'cafe', mark: 'T', color: '#c8102e', address: '회기로 190', lat: 37.5891, lng: 127.0558 },
  { id: 's_cafe_mega', brand: '메가커피', branch: '회기역점', category: 'cafe', mark: 'M', color: '#ffce00', address: '회기로 186', lat: 37.5896, lng: 127.0555 },
  { id: 's_cafe_compose', brand: '컴포즈커피', branch: '회기점', category: 'cafe', mark: 'C', color: '#1a1a1a', address: '회기로 192', lat: 37.5899, lng: 127.0570 },
  { id: 's_cafe_paik', brand: '빽다방', branch: '회기역점', category: 'cafe', mark: 'B', color: '#ffdd00', address: '회기로 184', lat: 37.5888, lng: 127.0548 },

  // ═══ 음식점 ═══
  { id: 's_rest_kimbap', brand: '김밥천국', branch: '회기점', category: 'restaurant', mark: '김', color: '#e8552d', address: '회기로 189', lat: 37.5895, lng: 127.0560 },
  { id: 's_rest_bbq', brand: 'BBQ', branch: '회기점', category: 'restaurant', mark: 'B', color: '#c8102e', address: '회기로 193', lat: 37.5897, lng: 127.0572 },
  { id: 's_rest_hansot', brand: '한솥', branch: '회기역점', category: 'restaurant', mark: '한', color: '#e60012', address: '회기로 185', lat: 37.5887, lng: 127.0550 },
  { id: 's_rest_momstouch', brand: '맘스터치', branch: '회기점', category: 'restaurant', mark: 'M', color: '#ed1c24', address: '회기로 197', lat: 37.5903, lng: 127.0578 },
  { id: 's_rest_dakgalbi', brand: '', branch: '회기참숯불닭갈비', category: 'restaurant', mark: '닭', color: '#a0522d', address: '회기로 183', lat: 37.5885, lng: 127.0543 },
  { id: 's_rest_kalguksu', brand: '', branch: '경희칼국수', category: 'restaurant', mark: '칼', color: '#5b8c5a', address: '이문로 50', lat: 37.5908, lng: 127.0582 },

  // ═══ 경영대 제휴 매장 (정적 — 자동수집 누락 방지) ═══
  { id: 'khu_mugam', brand: '', branch: '무감커피바', category: 'cafe', mark: '☕', color: '#6b4226', address: '서울 동대문구 회기로21길 19 B1층', lat: 37.5920, lng: 127.0540 },
  { id: 'khu_wayo', brand: '', branch: '와요', category: 'cafe', mark: '☕', color: '#e07c4c', address: '서울 동대문구 경희대로4길 7 1층', lat: 37.5938, lng: 127.0518 },
  { id: 'khu_8beonga', brand: '', branch: '8번가', category: 'cafe', mark: '8', color: '#2d6b4e', address: '서울 동대문구 경희대로3길 8 1층', lat: 37.5935, lng: 127.0512 },
  { id: 'khu_solidworks', brand: '', branch: '솔리드웍스 경희대점', category: 'cafe', mark: '☕', color: '#3a3a3a', address: '서울 동대문구 회기로26길 6 1층', lat: 37.5918, lng: 127.0555 },
  { id: 'khu_shimpresso', brand: '', branch: '쉼프레소티하우스', category: 'cafe', mark: '☕', color: '#8b5e3c', address: '서울 동대문구 경희대로 26', lat: 37.5945, lng: 127.0520 },
  { id: 'khu_ppangssem', brand: '', branch: '빵쌤', category: 'cafe', mark: '🍞', color: '#d4a373', address: '서울 동대문구 경희대로 4-1 1층', lat: 37.5930, lng: 127.0515 },
  { id: 'khu_gamdong', brand: '', branch: '감동', category: 'cafe', mark: '☕', color: '#c75b39', address: '서울 동대문구 회기로25길 101-13 1층', lat: 37.5912, lng: 127.0560 },
  { id: 'khu_heavybear', brand: '', branch: '헤비베어', category: 'cafe', mark: '🐻', color: '#5c3317', address: '서울 동대문구 경희대로6길 11-1 1층', lat: 37.5942, lng: 127.0528 },
  { id: 'khu_stay_tempo', brand: '', branch: '스테이 템포', category: 'cafe', mark: '☕', color: '#4a7c59', address: '서울 동대문구 경희대로4길 38 1층', lat: 37.5940, lng: 127.0520 },
  { id: 'khu_knock', brand: '', branch: '넉', category: 'restaurant', mark: '🍺', color: '#6b3a2a', address: '서울 동대문구 경희대로1길 8-13 1층', lat: 37.5928, lng: 127.0508 },
  { id: 'khu_rainbow', brand: '', branch: '무지개맥주 경희대점', category: 'restaurant', mark: '🍺', color: '#ff6b6b', address: '서울 동대문구 경희대로1길 9 1층', lat: 37.5929, lng: 127.0509 },
  { id: 'khu_sseassen', brand: '', branch: '씨쎈샌드', category: 'restaurant', mark: '🍺', color: '#e8a87c', address: '서울 동대문구 경희대로1길 8-7 1층', lat: 37.5928, lng: 127.0507 },
  { id: 'khu_kkulkkul', brand: '', branch: '꿀꿀이 닭갈비 외대점', category: 'restaurant', mark: '🍗', color: '#d63031', address: '서울 동대문구 천장산로32-1 B1층', lat: 37.5955, lng: 127.0600 },
  { id: 'khu_eoheung', brand: '', branch: '어흥식당', category: 'restaurant', mark: '🦁', color: '#e17055', address: '서울 동대문구 회기로13길 22 1층', lat: 37.5905, lng: 127.0535 },
  { id: 'khu_deungchon', brand: '', branch: '등촌샤브칼국수 경희대점', category: 'restaurant', mark: '🍲', color: '#0984e3', address: '서울 동대문구 회기로21길 38 1층', lat: 37.5922, lng: 127.0545 },
  { id: 'khu_yukcho', brand: '', branch: '육초연', category: 'restaurant', mark: '🥩', color: '#d63031', address: '서울 동대문구 회기로13길 24 1층', lat: 37.5906, lng: 127.0536 },
  { id: 'khu_neoknok', brand: '', branch: '넉넉', category: 'restaurant', mark: '🍖', color: '#6c5ce7', address: '서울 동대문구 경희대로4길 22 1층 102호', lat: 37.5937, lng: 127.0517 },
  { id: 'khu_goheung', brand: '', branch: '고흥소곱창', category: 'restaurant', mark: '🔥', color: '#fd79a8', address: '서울 동대문구 휘경로2가길 1 1층', lat: 37.5950, lng: 127.0615 },
  { id: 'khu_pocketz', brand: '', branch: '포켓츠', category: 'convenience', mark: '🎱', color: '#00b894', address: '서울 동대문구 회기로 113 1층', lat: 37.5900, lng: 127.0500 },

  // ═══ 비식음료 편의시설 (혜택 조건은 참고 데이터로 별도 관리) ═══
  { id: 'facility_lotte_cinema', brand: '롯데시네마', branch: '청량리점', category: 'culture', mark: '🎬', color: '#e60012', address: '서울 동대문구 왕산로 214', lat: 37.5807, lng: 127.0484 },
  { id: 'facility_cgv_wangsimni', brand: 'CGV', branch: '왕십리점', category: 'culture', mark: '🎬', color: '#f97316', address: '서울 성동구 왕십리광장로 17', lat: 37.5614, lng: 127.0384 },
  { id: 'facility_cgv_yongsan', brand: 'CGV', branch: '용산아이파크몰점', category: 'culture', mark: '🎬', color: '#f97316', address: '서울 용산구 한강대로23길 55', lat: 37.5298, lng: 126.9648 },
  { id: 'facility_megabox_dongdaemun', brand: '메가박스', branch: '동대문점', category: 'culture', mark: '🎬', color: '#351f66', address: '서울 중구 장충단로 247', lat: 37.5668, lng: 127.0078 },
  { id: 'facility_megabox_coex', brand: '메가박스', branch: '코엑스점', category: 'culture', mark: '🎬', color: '#351f66', address: '서울 강남구 봉은사로 524', lat: 37.5125, lng: 127.0588 },
  { id: 'facility_khu_bookstore', brand: '', branch: '경희대학교 구내서점', category: 'campus', mark: '책', color: '#4f46e5', address: '경희대학교 서울캠퍼스 청운관', lat: 37.5948, lng: 127.0520 },
  { id: 'facility_khu_copy', brand: '', branch: '경희대 복사실', category: 'campus', mark: 'P', color: '#7c3aed', address: '경희대학교 서울캠퍼스', lat: 37.5954, lng: 127.0533 },
  { id: 'facility_emart_everyday', brand: '이마트에브리데이', branch: '이문점', category: 'lifestyle', mark: 'E', color: '#f59e0b', address: '서울 동대문구 이문동 일대', lat: 37.5982, lng: 127.0614 },
  { id: 'facility_daiso_hoegi', brand: '다이소', branch: '회기역점', category: 'lifestyle', mark: 'D', color: '#e6002d', address: '서울 동대문구 회기로 일대', lat: 37.5894, lng: 127.0565 },
  { id: 'facility_oliveyoung_hoegi', brand: '올리브영', branch: '회기역점', category: 'lifestyle', mark: 'O', color: '#84bd00', address: '서울 동대문구 회기로 일대', lat: 37.5897, lng: 127.0558 },
  { id: 'facility_laundry', brand: '', branch: '회기 셀프빨래방', category: 'lifestyle', mark: 'W', color: '#0ea5e9', address: '서울 동대문구 회기동', lat: 37.5905, lng: 127.0527 },
]

// ─── 혜택 데이터 (paymentMethodId → 매장/브랜드/업종 매칭) ───
// 필드 설명:
//   type: 'percent'(즉시할인) | 'fixed'(정액할인) | 'cashback'(캐시백) | 'point'(적립)
//   value: 할인율(%) 또는 정액(원)
//   max: 1회 결제당 최대 할인액(원) — 없으면 무제한
//   monthlyCap: 월 최대 혜택액(원) — 표시용 (카드/멤버십 월한도)
//   stackable: 다른 혜택과 중복 가능 여부
//   verified: true=공식 출처 확인됨 / false=예시(팀 조사 후 확정 필요)
//   validUntil: 혜택 유효기한(YYYY-MM-DD) — 지나면 자동 '만료' 처리
//   lastChecked: 최종 확인일(YYYY-MM-DD)
//
// ▼ 아래 BENEFITS는 '오프라인 폴백/시드' 데이터.
//   실제 운영값은 외부 소스(benefits.json → 추후 서버 API)에서 불러와 덮어씀.
//   setBenefits()로 런타임 교체 가능. (app.js의 loadBenefits 참고)
let BENEFITS = [
  // ═══ 학생증 (경희대 제휴 — 팀 조사 후 확정 필요) ═══
  { id: 'b_tok_twosome', method: 'khu_alliance', brand: '투썸플레이스', type: 'percent', value: 10, stackable: false, cond: '음료 한정, 1일 1회', evidence: '경희대 총학생회 제휴 공지(예시)', verified: false },
  { id: 'b_tok_mega', method: 'khu_alliance', brand: '메가커피', type: 'fixed', value: 300, stackable: false, cond: '전 음료 300원 할인', evidence: '경희대 총학생회 제휴 공지(예시)', verified: false },
  { id: 'b_tok_bbq', method: 'khu_alliance', brand: 'BBQ', type: 'percent', value: 5, max: 2000, stackable: false, cond: '매장 식사, 포장/배달 제외', evidence: '경희대 총학생회 제휴 공지(예시)', verified: false },
  { id: 'b_card_paik', method: 'student_card', brand: '빽다방', type: 'fixed', value: 500, stackable: false, cond: '음료 1잔당 500원, 학생증 제시', evidence: '매장 학생증 할인 안내문(예시)', verified: false },
  // 경희대 개별 제휴 매장(로컬) — 매장명 부분일치로 매칭. 팀 수집 데이터로 교체/추가.
  { id: 'b_khu_dakgalbi', method: 'khu_alliance', nameIncludes: ['참숯불닭갈비', '닭갈비'], type: 'percent', value: 10, stackable: false, cond: '경희대 제휴, 학생증 제시(예시)', evidence: '총학/단과대 제휴(예시 — 확인 필요)', verified: false },
  { id: 'b_khu_kalguksu', method: 'khu_alliance', nameIncludes: ['경희칼국수', '칼국수'], type: 'fixed', value: 1000, stackable: false, cond: '경희대 제휴, 1만원 이상(예시)', evidence: '총학/단과대 제휴(예시 — 확인 필요)', verified: false },

  // ═══ 통신사 - SKT (정확한 % / 한도 조사 후 확정 필요) ═══
  { id: 'b_skt_cu', method: 'telecom_skt', brand: 'CU', type: 'percent', value: 7, max: 3000, monthlyCap: 9000, stackable: true, cond: 'VIP콕, 월 3회', evidence: 'T멤버십 앱(예시)', verified: false },
  { id: 'b_skt_gs', method: 'telecom_skt', brand: 'GS25', type: 'percent', value: 7, max: 3000, monthlyCap: 9000, stackable: true, cond: 'VIP콕, 월 3회', evidence: 'T멤버십 앱(예시)', verified: false },
  { id: 'b_skt_twosome', method: 'telecom_skt', brand: '투썸플레이스', type: 'percent', value: 20, max: 4000, stackable: true, cond: 'T day(화) / VIP콕, 월 2~3회', evidence: 'T멤버십 앱(예시)', verified: false },
  { id: 'b_skt_mega', method: 'telecom_skt', brand: '메가커피', type: 'percent', value: 10, max: 2000, stackable: true, cond: 'T멤버십 상시 할인', evidence: 'T멤버십 앱(예시)', verified: false },

  // ═══ 통신사 - KT ═══
  { id: 'b_kt_gs', method: 'telecom_kt', brand: 'GS25', type: 'percent', value: 10, max: 3000, monthlyCap: 6000, stackable: true, cond: 'KT 슈퍼할인, 월 2회', evidence: 'MY KT 앱(예시)', verified: false },
  { id: 'b_kt_twosome', method: 'telecom_kt', brand: '투썸플레이스', type: 'percent', value: 15, max: 3000, stackable: true, cond: 'KT 카페 할인, 월 2회', evidence: 'MY KT 앱(예시)', verified: false },
  { id: 'b_kt_bbq', method: 'telecom_kt', brand: 'BBQ', type: 'percent', value: 7, max: 3000, stackable: true, cond: 'KT 외식 카테고리, 월 2회', evidence: 'MY KT 앱(예시)', verified: false },

  // ═══ 통신사 - LG U+ ═══
  { id: 'b_lgu_cu', method: 'telecom_lgu', brand: 'CU', type: 'percent', value: 5, max: 2000, monthlyCap: 6000, stackable: true, cond: 'U+멤버십 편의점, 월 3회', evidence: '당신의 U+ 앱(예시)', verified: false },
  { id: 'b_lgu_seven', method: 'telecom_lgu', brand: '세븐일레븐', type: 'percent', value: 7, max: 2000, stackable: true, cond: 'U+멤버십 세븐일레븐, 월 3회', evidence: '당신의 U+ 앱(예시)', verified: false },
  { id: 'b_lgu_compose', method: 'telecom_lgu', brand: '컴포즈커피', type: 'percent', value: 10, max: 2000, stackable: true, cond: 'U+멤버십 카페, 월 2회', evidence: '당신의 U+ 앱(예시)', verified: false },

  // ═══ 페이 ═══
  { id: 'b_kakao_conv', method: 'pay_kakao', storeCategory: 'convenience', type: 'cashback', value: 2, max: 1000, monthlyCap: 3000, stackable: true, cond: '현장결제(QR) 페이백, 이벤트성(월변동)', evidence: '카카오페이 앱 이벤트(2026.08, 예시)', verified: false },
  { id: 'b_kakao_cafe', method: 'pay_kakao', storeCategory: 'cafe', type: 'cashback', value: 2, max: 1000, monthlyCap: 3000, stackable: true, cond: '현장결제(QR) 페이백, 이벤트성(월변동)', evidence: '카카오페이 앱 이벤트(2026.08, 예시)', verified: false },
  { id: 'b_naver_cu', method: 'pay_naver', brand: 'CU', type: 'percent', value: 10, max: 10000, requiresNaverPlus: true, stackable: true, cond: 'CU QR결제 5% 할인(최대 5천원)+5% 적립(최대 5천원), 각각 1일1회, 삼성페이 제외', evidence: '네이버플러스 멤버십 공식 고객센터', sourceUrl: 'https://help.naver.com/service/23168/contents/23131?lang=ko&osType=COMMONOS', verified: true },
  { id: 'b_kakao_gooddeal_cu', method: 'pay_kakao', brand: 'CU', type: 'percent', value: 6, max: 2000, stackable: true, cond: '카카오페이 굿딜 CU 6% (딜 변동)', evidence: '카카오페이 굿딜(변동)', verified: false },
  { id: 'b_kakao_plus_cafe', method: 'pay_kakao', storeCategory: 'cafe', type: 'cashback', value: 5, max: 2000, requiresKakaoPlus: true, stackable: true, cond: '카카오페이 플러스 전용 카페 5%(예시)', evidence: '카카오페이 플러스 멤버십(예시)', verified: false },
  { id: 'b_naver_rest', method: 'pay_naver', storeCategory: 'restaurant', type: 'point', value: 1, stackable: true, cond: '현장결제 기본 1% 주장 — 공식 적용 범위 확인 필요', evidence: '공식 상세 URL 미확보', verified: false, calculable: false },
  { id: 'b_naver_cafe', method: 'pay_naver', storeCategory: 'cafe', type: 'point', value: 1, stackable: true, cond: '현장결제 기본 1% 주장 — 공식 적용 범위 확인 필요', evidence: '공식 상세 URL 미확보', verified: false, calculable: false },
  { id: 'b_toss_conv', method: 'pay_toss', storeCategory: 'convenience', type: 'cashback', value: 5, max: 2000, stackable: true, cond: '토스 앱 결제 혜택의 대상 브랜드·기간·사용자 조건 확인 필요', evidence: '토스페이 프로모션 MVP 후보 데이터', verified: false, calculable: false },
  { id: 'b_toss_cafe', method: 'pay_toss', storeCategory: 'cafe', type: 'cashback', value: 5, max: 2000, stackable: true, cond: '토스 앱 결제 혜택의 대상 카페·기간·사용자 조건 확인 필요', evidence: '토스페이 프로모션 MVP 후보 데이터', verified: false, calculable: false },
  { id: 'b_toss_rest', method: 'pay_toss', storeCategory: 'restaurant', type: 'cashback', value: 3, max: 2000, stackable: true, cond: '토스 앱 결제 혜택의 대상 음식점·기간·사용자 조건 확인 필요', evidence: '토스페이 프로모션 MVP 후보 데이터', verified: false, calculable: false },
  { id: 'b_toss_lifestyle', method: 'pay_toss', storeCategory: 'lifestyle', type: 'cashback', value: 5, max: 2000, stackable: true, cond: '토스 앱 결제 혜택의 대상 생활편의 매장·기간 확인 필요', evidence: '토스페이 프로모션 MVP 후보 데이터', verified: false, calculable: false },

  // ═══ 카드 - KB (상품설명서 수치 확인 필요) ═══
  { id: 'b_kb_nara_conv', method: 'kb_narasarang', storeCategory: 'convenience', type: 'cashback', value: 5, max: 2000, monthlyCap: 2000, stackable: true, cond: '전월실적 30만원↑ · 월 최대 2천원', evidence: 'KB 나라사랑카드 상품설명서(예시)', verified: false },
  { id: 'b_kb_peng_cafe', method: 'kb_pengsoo', storeCategory: 'cafe', type: 'cashback', value: 10, perTxMax: 2000, monthlyCap: 5000, prevSpend: 200000, excludeBrands: ['스타벅스'], stackable: true, cond: '스타벅스 제외 · 전월실적 20만원↑ · 월 최대 5천원', evidence: 'KB 펭수노리 체크카드(예시)', verified: false },
  { id: 'b_kb_peng_conv', method: 'kb_pengsoo', storeCategory: 'convenience', type: 'cashback', value: 5, max: 2000, monthlyCap: 5000, stackable: true, cond: '전월실적 20만원↑ · 월 최대 5천원', evidence: 'KB 펭수노리 체크카드(예시)', verified: false },

  // ═══ 카드 - 하나 ═══
  { id: 'b_hana_naver_cafe', method: 'hana_naverpay', storeCategory: 'cafe', type: 'point', value: 1, stackable: true, cond: '네이버포인트 오프라인 1% 적립', evidence: '하나 네이버페이머니 체크카드(예시)', verified: false },
  { id: 'b_hana_naver_conv', method: 'hana_naverpay', storeCategory: 'convenience', type: 'point', value: 1, stackable: true, cond: '네이버포인트 1% 적립', evidence: '하나 네이버페이머니 체크카드(예시)', verified: false },
  { id: 'b_hana_nara_conv', method: 'hana_narasarang', storeCategory: 'convenience', type: 'cashback', value: 5, max: 2000, monthlyCap: 2000, stackable: true, cond: '전월실적 20만원↑ · 월 최대 2천원', evidence: '하나 나라사랑카드(예시)', verified: false },

  // ═══ 카드 - 기업 ═══
  { id: 'b_ibk_rest', method: 'ibk_easy_cashback', storeCategory: 'restaurant', type: 'cashback', value: 3, max: 3000, monthlyCap: 5000, stackable: true, cond: '외식 추가적립 · 전월실적 30만원↑ · 월 최대 5천원', evidence: 'IBK EASY Cashback 체크카드(예시)', verified: false },
  { id: 'b_ibk_cafe', method: 'ibk_easy_cashback', storeCategory: 'cafe', type: 'cashback', value: 2, max: 2000, monthlyCap: 5000, stackable: true, cond: '커피전문점 2% · 전월실적 30만원↑ · 월 최대 5천원', evidence: 'IBK EASY Cashback 체크카드(예시)', verified: false },

  // ═══ 지역화폐 - 서울사랑상품권 (동대문구 = 서울사랑상품권 권역) ═══
  // 서울사랑상품권은 '충전 시 할인구매'가 이득의 본질 (제로페이/서울Pay+ 가맹점에서만 사용)
  // 상시 할인율은 예산에 따라 변동(과거 5~10%) → 서울Pay+ 앱에서 재확인 필요
  { id: 'b_seoul_rest', method: 'local_seoul', requiredStoreFlag: 'seoulPay', storeCategory: 'restaurant', type: 'percent', value: 5, max: 100000, stackable: false, cond: '동대문구사랑상품권 구매 시 5% 할인 · 서울Pay+ 가맹 확인 매장', evidence: '서울Pay+ 앱 + 가맹점 원본', verified: true },
  { id: 'b_seoul_cafe', method: 'local_seoul', requiredStoreFlag: 'seoulPay', storeCategory: 'cafe', type: 'percent', value: 5, max: 100000, stackable: false, cond: '동대문구사랑상품권 구매 시 5% 할인 · 서울Pay+ 가맹 확인 매장', evidence: '서울Pay+ 앱 + 가맹점 원본', verified: true },
  { id: 'b_seoul_conv', method: 'local_seoul', requiredStoreFlag: 'seoulPay', storeCategory: 'convenience', type: 'percent', value: 5, max: 100000, stackable: false, cond: '동대문구사랑상품권 구매 시 5% 할인 · 점포별 서울Pay+ 가맹 확인', evidence: '서울Pay+ 앱 + 가맹점 원본', verified: true },

  // ═══ 지역화폐 - 온누리 (디지털 가맹 확인, 할인율 재확인 필요) ═══
  { id: 'b_onnuri_rest', method: 'local_onnuri', requiredStoreFlag: 'onnuriDigital', storeCategory: 'restaurant', type: 'percent', value: 5, max: 100000, stackable: false, cond: '디지털 온누리 가맹 확인 · 현재 할인율 공식 근거 재확인 필요', evidence: '가맹점 CSV 확보, 현재 할인율 공식 근거 미확보', verified: false, calculable: false },
  { id: 'b_onnuri_conv', method: 'local_onnuri', requiredStoreFlag: 'onnuriDigital', storeCategory: 'convenience', type: 'percent', value: 5, max: 100000, stackable: false, cond: '점포별 디지털 온누리 가맹 확인 · 현재 할인율 공식 근거 재확인 필요', evidence: '가맹점 CSV 확보, 현재 할인율 공식 근거 미확보', verified: false, calculable: false },
]

// 외부 소스(benefits.json/서버)에서 불러온 데이터로 런타임 교체
function setBenefits(arr) {
  if (Array.isArray(arr) && arr.length) BENEFITS = arr
}
