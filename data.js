// ═══════════════════════════════════════════════════════════
// 페이픽 + 거지앱 통합 데이터 (2026-08 기준 MVP 예시)
// 범위: 경희대 ~ 회기역 ~ 외대앞 일대
// ═══════════════════════════════════════════════════════════

// ─── 결제수단 후보군 (온보딩에서 선택) ───
const PAYMENT_GROUPS = [
  {
    category: 'student_id',
    label: '학생증',
    emoji: '🎓',
    methods: [
      { id: 'student_tok', name: '톡학생증', issuer: '경희대' },
      { id: 'student_card', name: '학생증카드', issuer: '경희대' },
    ],
  },
  {
    category: 'telecom',
    label: '통신사',
    emoji: '📡',
    methods: [
      { id: 'telecom_skt', name: 'T멤버십', issuer: 'SKT' },
      { id: 'telecom_kt', name: 'KT멤버십', issuer: 'KT' },
      { id: 'telecom_lgu', name: 'U+멤버십', issuer: 'LG U+' },
    ],
  },
  {
    category: 'pay',
    label: '페이',
    emoji: '📱',
    methods: [
      { id: 'pay_kakao', name: '카카오페이', issuer: '카카오' },
      { id: 'pay_naver', name: '네이버페이', issuer: '네이버' },
      { id: 'pay_danggeun', name: '당근페이', issuer: '당근' },
    ],
  },
  {
    category: 'card',
    label: '카드',
    emoji: '💳',
    methods: [
      { id: 'kb_narasarang', name: '나라사랑카드', issuer: 'KB' },
      { id: 'kb_pengsoo', name: '펭수 노리 카드', issuer: 'KB' },
      { id: 'hana_naverpay', name: '네이버페이머니', issuer: '하나' },
      { id: 'hana_narasarang', name: '나라사랑카드', issuer: '하나' },
      { id: 'ibk_easy_cashback', name: 'EASY Cashback', issuer: '기업' },
    ],
  },
  {
    category: 'local_currency',
    label: '지역화폐',
    emoji: '🏘️',
    methods: [
      { id: 'local_seoul', name: '서울사랑상품권', issuer: '서울시' },
      { id: 'local_onnuri', name: '온누리상품권', issuer: '소상공인시장진흥공단' },
    ],
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
  student_id: '학생증',
  telecom: '통신사',
  pay: '페이',
  card: '카드',
  local_currency: '지역화폐',
}

// ─── 매장 데이터 (편의점 + 카페 + 음식점) ───
// storeCategory: 'convenience' | 'cafe' | 'restaurant'
const STORES = [
  // ═══ 편의점 (페이픽 기존 데이터) ═══
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
  { id: 'b_tok_twosome', method: 'student_tok', brand: '투썸플레이스', type: 'percent', value: 10, stackable: false, cond: '음료 한정, 1일 1회', evidence: '경희대 총학생회 제휴 공지(예시)', verified: false },
  { id: 'b_tok_mega', method: 'student_tok', brand: '메가커피', type: 'fixed', value: 300, stackable: false, cond: '전 음료 300원 할인', evidence: '경희대 총학생회 제휴 공지(예시)', verified: false },
  { id: 'b_tok_bbq', method: 'student_tok', brand: 'BBQ', type: 'percent', value: 5, max: 2000, stackable: false, cond: '매장 식사, 포장/배달 제외', evidence: '경희대 총학생회 제휴 공지(예시)', verified: false },
  { id: 'b_card_paik', method: 'student_card', brand: '빽다방', type: 'fixed', value: 500, stackable: false, cond: '음료 1잔당 500원, 학생증 제시', evidence: '매장 학생증 할인 안내문(예시)', verified: false },
  // 경희대 개별 제휴 매장(로컬) — 매장명 부분일치로 매칭. 팀 수집 데이터로 교체/추가.
  { id: 'b_khu_dakgalbi', method: 'student_tok', nameIncludes: ['참숯불닭갈비', '닭갈비'], type: 'percent', value: 10, stackable: false, cond: '경희대 제휴, 학생증 제시(예시)', evidence: '총학/단과대 제휴(예시 — 확인 필요)', verified: false },
  { id: 'b_khu_kalguksu', method: 'student_tok', nameIncludes: ['경희칼국수', '칼국수'], type: 'fixed', value: 1000, stackable: false, cond: '경희대 제휴, 1만원 이상(예시)', evidence: '총학/단과대 제휴(예시 — 확인 필요)', verified: false },

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
  { id: 'b_naver_cu', method: 'pay_naver', brand: 'CU', type: 'percent', value: 10, max: 1000, requiresNaverPlus: true, stackable: true, cond: '네이버플러스 멤버십 전용, CU QR결제, 1일1회', evidence: '네이버 고객센터: 플러스 멤버십 CU 최대 10%', verified: true },
  { id: 'b_kakao_gooddeal_cu', method: 'pay_kakao', brand: 'CU', type: 'percent', value: 6, max: 2000, stackable: true, cond: '카카오페이 굿딜 CU 6% (딜 변동)', evidence: '카카오페이 굿딜(변동)', verified: false },
  { id: 'b_kakao_plus_cafe', method: 'pay_kakao', storeCategory: 'cafe', type: 'cashback', value: 5, max: 2000, requiresKakaoPlus: true, stackable: true, cond: '카카오페이 플러스 전용 카페 5%(예시)', evidence: '카카오페이 플러스 멤버십(예시)', verified: false },
  { id: 'b_naver_rest', method: 'pay_naver', storeCategory: 'restaurant', type: 'point', value: 1, stackable: true, cond: '현장결제 기본 적립(비멤버십 포함)', evidence: '네이버페이 포인트 적립 안내', verified: true },
  { id: 'b_naver_cafe', method: 'pay_naver', storeCategory: 'cafe', type: 'point', value: 1, stackable: true, cond: '현장결제 기본 적립(비멤버십 포함)', evidence: '네이버페이 포인트 적립 안내', verified: true },
  { id: 'b_danggeun_conv', method: 'pay_danggeun', storeCategory: 'convenience', type: 'cashback', value: 3, max: 2000, stackable: true, cond: '현장결제(QR) 신규 프로모션, 소규모 매장', evidence: '당근페이 현장결제 프로모션(예시)', verified: false },

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
  { id: 'b_seoul_rest', method: 'local_seoul', storeCategory: 'restaurant', type: 'cashback', value: 7, max: 100000, stackable: false, cond: '충전 시 7% 할인구매(율 변동) · 제로페이/서울Pay+ 가맹점만', evidence: '서울사랑상품권 서울Pay+ (율 변동, 재확인 필요)', verified: false },
  { id: 'b_seoul_cafe', method: 'local_seoul', storeCategory: 'cafe', type: 'cashback', value: 7, max: 100000, stackable: false, cond: '충전 시 7% 할인구매(율 변동) · 제로페이 가맹점만 · 대형 프랜차이즈 다수 제외', evidence: '서울사랑상품권 서울Pay+ (율 변동, 재확인 필요)', verified: false },
  { id: 'b_seoul_conv', method: 'local_seoul', storeCategory: 'convenience', type: 'cashback', value: 7, max: 100000, stackable: false, cond: '충전 시 7% 할인구매(율 변동) · 점포별 제로페이 가맹 여부 상이', evidence: '서울사랑상품권 서울Pay+ (율 변동, 재확인 필요)', verified: false },

  // ═══ 지역화폐 - 온누리 (평상시 5% 할인구매, 명절 10%) ═══
  { id: 'b_onnuri_rest', method: 'local_onnuri', storeCategory: 'restaurant', type: 'cashback', value: 5, max: 100000, stackable: false, cond: '평상시 5% 할인구매(명절 10%) · 전통시장/골목상권 가맹점만 · 월 구매한도', evidence: '소상공인시장진흥공단 온누리상품권(평상시 5%)', verified: true },
  { id: 'b_onnuri_conv', method: 'local_onnuri', storeCategory: 'convenience', type: 'cashback', value: 5, max: 100000, stackable: false, cond: '전통시장 인근 소형 편의점만 · 대형 프랜차이즈 불가', evidence: '소상공인시장진흥공단 온누리상품권(평상시 5%)', verified: true },
]

// 외부 소스(benefits.json/서버)에서 불러온 데이터로 런타임 교체
function setBenefits(arr) {
  if (Array.isArray(arr) && arr.length) BENEFITS = arr
}
