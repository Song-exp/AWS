// ═══════════════════════════════════════════════════════════
// 최적 결제수단 추천 엔진
// "추천대로 결제하면 실제로 그만큼 할인" 을 보장하기 위해
// 카드/멤버십의 실제 규칙을 반영해서 계산한다.
//
// 혜택(benefit) 필드 규격:
//   type        : 'percent'|'fixed'|'cashback'|'point'
//   value       : 할인율(%) 또는 정액(원)
//   minSpend    : 이 금액 미만이면 혜택 미적용 (원)
//   perTxMax    : 1회 결제당 최대 할인/적립액 (원)
//   monthlyCap  : 월 통합 한도 (원) — 표시 + 월 누적 계산용
//   prevSpend   : 전월실적 요건 (원) — 미충족 시 혜택 0
//   excludeBrands: 제외 브랜드 배열 (예: ['스타벅스'])
//   stackable   : 다른 혜택과 중복 가능 여부
//   verified    : true=공식출처 확인 / false=예시(확정 전)
// ═══════════════════════════════════════════════════════════

// 특정 혜택이 특정 매장에 적용되는지 판별
function benefitApplies(benefit, store) {
  // 제외 브랜드
  if (benefit.excludeBrands && store.brand && benefit.excludeBrands.includes(store.brand)) {
    return false
  }
  // 매장명 부분일치 (경희대 제휴처럼 개별 로컬 매장을 이름으로 지정)
  if (benefit.nameIncludes) {
    const target = (store.name || store.branch || '')
    return benefit.nameIncludes.some(kw => target.includes(kw))
  }
  if (benefit.storeId) return benefit.storeId === store.id
  if (benefit.brand) return store.brand && benefit.brand === store.brand
  if (benefit.storeCategory) return benefit.storeCategory === store.category
  return false
}

// 혜택 1건의 예상 절약액 계산
// opts.prevSpendMet: 전월실적 충족으로 가정할지 (기본 true = 데모)
// opts.monthlyUsed: 이번 달 이미 사용한 해당 혜택 누적액 (기본 0)
function benefitSaving(benefit, spend, opts = {}) {
  const { prevSpendMet = true, monthlyUsed = 0 } = opts

  // 전월실적 요건 미충족 시 혜택 없음
  if (benefit.prevSpend && !prevSpendMet) return 0
  // 최소 결제금액 미달
  if (benefit.minSpend && spend < benefit.minSpend) return 0

  let saving = 0
  switch (benefit.type) {
    case 'percent':
    case 'cashback':
    case 'point':
      saving = Math.floor(spend * (benefit.value / 100))
      break
    case 'fixed':
      saving = benefit.value
      break
  }

  // 1회 결제당 한도
  if (benefit.perTxMax && saving > benefit.perTxMax) saving = benefit.perTxMax
  if (benefit.max && saving > benefit.max) saving = benefit.max // 하위호환

  // 월 통합 한도 (남은 한도까지만)
  if (benefit.monthlyCap != null) {
    const remain = Math.max(0, benefit.monthlyCap - monthlyUsed)
    if (saving > remain) saving = remain
  }

  return saving
}

// 혜택 표시 문구
function benefitLabel(benefit) {
  switch (benefit.type) {
    case 'percent': return `${benefit.value}% 할인`
    case 'fixed': return `${benefit.value.toLocaleString()}원 할인`
    case 'cashback': return `${benefit.value}% 캐시백`
    case 'point': return `${benefit.value}% 적립`
  }
  return ''
}

/**
 * 매장에 대해 보유 결제수단별 혜택을 계산하고 절약액 순으로 정렬
 * @returns [{ method, benefit, saving, label }]
 */
function todayStr() {
  return new Date().toISOString().slice(0, 10)
}
// 유효기간 지난 혜택은 비활성(추천에서 자동 제외)
function isBenefitActive(b) {
  return !b.validUntil || b.validUntil >= todayStr()
}

// 사용자 프로필 조건 충족 여부
//   requiresNaverPlus: 네이버플러스 멤버십 필요
//   minGrade: 'vip'  → 통신사 VIP등급 이상만
//   onlyGrade: 'normal' → 일반등급 전용(Silver 등)
function requiresMet(b, profile) {
  const p = profile || {}
  if (b.requiresNaverPlus && !p.naverPlus) return false
  if (b.requiresKakaoPlus && !p.kakaoPlus) return false
  if (b.minGrade === 'vip' && (p.telecomGrade || 'vip') !== 'vip') return false
  if (b.onlyGrade === 'normal' && (p.telecomGrade || 'vip') !== 'normal') return false
  return true
}

function getRecommendations(store, ownedMethodIds, spend = 10000, opts = {}) {
  const profile = opts.profile || { naverPlus: false, telecomGrade: 'vip' }
  const recs = []
  for (const b of BENEFITS) {
    if (!ownedMethodIds.has(b.method)) continue
    if (!isBenefitActive(b)) continue
    if (!requiresMet(b, profile)) continue
    if (!benefitApplies(b, store)) continue
    const method = PAYMENT_METHODS[b.method]
    if (!method) continue
    recs.push({
      method,
      benefit: b,
      saving: benefitSaving(b, spend, opts),
      label: benefitLabel(b),
    })
  }
  // 절약액 큰 순, 동률이면 확인된(verified) 혜택 우선
  recs.sort((a, b) => (b.saving - a.saving) || ((b.benefit.verified ? 1 : 0) - (a.benefit.verified ? 1 : 0)))
  return recs
}

// 보유수단 기준으로, 매장이 (유효한) 혜택 하나라도 있는지
function storeHasBenefit(store, ownedMethodIds, profile) {
  return BENEFITS.some(b =>
    ownedMethodIds.has(b.method) &&
    isBenefitActive(b) &&
    requiresMet(b, profile) &&
    benefitApplies(b, store))
}

// ─── 최적 "조합" 계산 ───────────────────────────────────────
// 실제 결제 1건에는 아래가 동시에 겹칠 수 있음:
//   [할인 레이어] 학생증 제휴할인 + 통신사 멤버십 할인  (결제수단과 별개로 제시)
//   [결제 레이어] 페이 / 카드 / 지역화폐 중 '하나' (실제로 긁는 수단)
// 단, 어떤 혜택이 stackable:false 면 그 혜택은 단독으로만 사용 가능.
function computeBestPlan(store, ownedMethodIds, spend = 10000, opts = {}) {
  // 적용 가능한 (유효) 혜택 수집
  const applicable = getRecommendations(store, ownedMethodIds, spend, opts)
    .filter(r => r.saving > 0)
  if (applicable.length === 0) return { benefits: [], saving: 0 }

  const catOf = r => r.method.category
  const isPaymentLayer = c => c === 'pay' || c === 'card' || c === 'local_currency'

  // 후보1: 단독 최고 (비중첩 포함)
  const bestSingle = applicable.reduce((a, b) => (b.saving > a.saving ? b : a))

  // 후보2: 중첩 조합 (stackable 만)
  const stackables = applicable.filter(r => r.benefit.stackable)
  const bestOf = pred => stackables.filter(pred).reduce((a, b) => (!a || b.saving > a.saving ? b : a), null)

  const student = bestOf(r => catOf(r) === 'student_id')
  const telecom = bestOf(r => catOf(r) === 'telecom')
  const payment = bestOf(r => isPaymentLayer(catOf(r)))

  const comboParts = [student, telecom, payment].filter(Boolean)
  const comboSaving = comboParts.reduce((s, r) => s + r.saving, 0)

  // 조합이 단독보다 크면 조합, 아니면 단독
  if (comboParts.length >= 2 && comboSaving >= bestSingle.saving) {
    return { benefits: comboParts, saving: comboSaving, combo: true }
  }
  return { benefits: [bestSingle], saving: bestSingle.saving, combo: false }
}
