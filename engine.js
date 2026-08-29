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
  // 가맹점 원본을 통해 명시적으로 확인된 매장에서만 지역화폐를 허용한다.
  // 데이터 로드/매칭 실패 시 플래그가 true가 아니므로 자동으로 fail-closed 된다.
  if (benefit.requiredStoreFlag && store.localCurrency?.[benefit.requiredStoreFlag] !== true) {
    return false
  }
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
  if (benefit.brand) {
    if (store.brand && benefit.brand === store.brand) return true
    // 자동수집 매장에 아직 등록되지 않은 브랜드도 팀 CSV의 브랜드명으로 매칭한다.
    const normalize = value => String(value || '').toLowerCase().replace(/[^0-9a-z가-힣]/g, '')
    const storeName = normalize(store.name || store.branch)
    const benefitBrand = normalize(benefit.brand)
    return Boolean(benefitBrand && storeName.includes(benefitBrand))
  }
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

  const eligibleSpend = benefit.spendUnit
    ? Math.floor(spend / benefit.spendUnit) * benefit.spendUnit
    : spend

  let saving = 0
  switch (benefit.type) {
    case 'percent':
    case 'cashback':
    case 'point':
      saving = Math.floor(eligibleSpend * (benefit.value / 100))
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

// 금액 추천 허용 정책:
// 1) verified:true로 근거가 확인됐고
// 2) calculable:false가 아닌 경우에만 실제 절약액/순위 계산에 사용한다.
// 할인율은 맞아도 점포 가맹 여부·메뉴·쿠폰 조건을 확인할 수 없으면 calculable:false다.
function isBenefitRecommendable(b) {
  return b.verified === true && b.calculable !== false
}

function benefitMatchesUserAndStore(b, store, ownedMethodIds, profile) {
  return ownedMethodIds.has(b.method) &&
    isBenefitActive(b) &&
    requiresMet(b, profile) &&
    benefitApplies(b, store)
}

function recommendationRecord(b, spend, opts) {
  const method = PAYMENT_METHODS[b.method]
  if (!method) return null
  return {
    method,
    benefit: b,
    saving: benefitSaving(b, spend, opts),
    label: benefitLabel(b),
  }
}

function getRecommendations(store, ownedMethodIds, spend = 10000, opts = {}) {
  const profile = opts.profile || { naverPlus: false, telecomGrade: 'vip' }
  const recs = []
  for (const b of BENEFITS) {
    if (!isBenefitRecommendable(b)) continue
    if (!benefitMatchesUserAndStore(b, store, ownedMethodIds, profile)) continue
    const rec = recommendationRecord(b, spend, opts)
    if (rec) recs.push(rec)
  }
  recs.sort((a, b) => b.saving - a.saving)
  return recs
}

// 출처가 미검증이거나 점포/메뉴 등 계산 전제조건이 부족한 혜택.
// 절약액과 순위에는 절대 포함하지 않고 UI 참고 목록에만 제공한다.
function getReferenceRecommendations(store, ownedMethodIds, spend = 10000, opts = {}) {
  const profile = opts.profile || { naverPlus: false, telecomGrade: 'vip' }
  const recs = []
  for (const b of BENEFITS) {
    if (isBenefitRecommendable(b)) continue
    if (!benefitMatchesUserAndStore(b, store, ownedMethodIds, profile)) continue
    const rec = recommendationRecord(b, spend, opts)
    if (!rec) continue
    rec.referenceReason = b.verified !== true ? '공식 근거 확인 필요' : '적용 조건 확인 필요'
    recs.push(rec)
  }
  return recs
}

// 보유수단 기준으로 검증 혜택 또는 참고 혜택이 하나라도 있는 매장만 노출한다.
// requiresMet을 유지하므로 가입하지 않은 멤버십/등급 혜택으로 매장이 노출되지 않는다.
function storeHasBenefit(store, ownedMethodIds, profile) {
  return BENEFITS.some(b => benefitMatchesUserAndStore(b, store, ownedMethodIds, profile || {}))
}

// ─── 최적 "조합" 계산 ───────────────────────────────────────
// 실제 결제 1건에는 아래가 동시에 겹칠 수 있음:
//   [할인 레이어] 학생증 제휴할인 + 통신사 멤버십 할인  (결제수단과 별개로 제시)
//   [결제 레이어] 페이 / 카드 / 지역화폐 중 '하나' (실제로 긁는 수단)
// 단, 어떤 혜택이 stackable:false 면 그 혜택은 단독으로만 사용 가능.
function computeBestPlan(store, ownedMethodIds, spend = 10000, opts = {}) {
  // 적용 가능한 검증 완료 혜택만 수집
  const applicable = getRecommendations(store, ownedMethodIds, spend, opts)
    .filter(r => r.saving > 0)
  if (applicable.length === 0) return { benefits: [], saving: 0 }

  const catOf = r => r.method.category
  const isPaymentLayer = c => c === 'pay' || c === 'card' || c === 'local_currency'

  // 현금/계좌이체 전용 할인 분리
  const cashOnly = applicable.filter(r => r.benefit.payRestriction)
  const normal = applicable.filter(r => !r.benefit.payRestriction)

  // ── 방법 A: 현금 전용 제휴 할인 (카드/페이 적립 포기) ──
  const bestCash = cashOnly.length
    ? cashOnly.reduce((a, b) => b.saving > a.saving ? b : a)
    : null

  // ── 방법 B: 일반 조합 (통신사 할인 + 페이/카드 결제) ──
  const stackables = normal.filter(r => r.benefit.stackable)
  const bestOf = pred => stackables.filter(pred).reduce((a, b) => (!a || b.saving > a.saving ? b : a), null)

  const student = bestOf(r => catOf(r) === 'student_id')
  const telecom = bestOf(r => catOf(r) === 'telecom')
  const payment = bestOf(r => isPaymentLayer(catOf(r)))

  const discountParts = [student, telecom].filter(Boolean)
  const beforePaymentSaving = discountParts.reduce((sum, r) => sum + r.saving, 0)
  const adjustedPayment = payment
    ? {
        ...payment,
        // 학생/통신사 할인을 먼저 적용한 뒤 실제 결제되는 잔액 기준으로
        // 페이·카드·지역화폐 혜택을 계산해 단순 퍼센트 합산 과장을 막는다.
        saving: benefitSaving(payment.benefit, Math.max(0, spend - beforePaymentSaving), opts),
      }
    : null
  const comboParts = [...discountParts, adjustedPayment].filter(r => r && r.saving > 0)
  const comboSaving = comboParts.reduce((s, r) => s + r.saving, 0)

  // 단독 최고 (비중첩 포함, normal만)
  const bestSingle = normal.length
    ? normal.reduce((a, b) => (b.saving > a.saving ? b : a))
    : null

  // 일반 조합 vs 단독 중 더 큰 것
  let normalBest
  if (comboParts.length >= 2 && comboSaving >= (bestSingle?.saving || 0)) {
    normalBest = { benefits: comboParts, saving: comboSaving, combo: true }
  } else if (bestSingle) {
    normalBest = { benefits: [bestSingle], saving: bestSingle.saving, combo: false }
  } else {
    normalBest = { benefits: [], saving: 0 }
  }

  // ── 최종 비교: 현금 전용 vs 검증된 비현금 조합 ──
  if (bestCash && bestCash.saving > normalBest.saving) {
    return {
      benefits: [bestCash],
      saving: bestCash.saving,
      combo: false,
      cashRestricted: true,
      comparison: `현금/계좌이체 ${bestCash.saving.toLocaleString()}원 할인 vs 검증된 비현금 혜택 ${normalBest.saving.toLocaleString()}원 → 현금이 ${(bestCash.saving - normalBest.saving).toLocaleString()}원 이득`,
    }
  } else if (bestCash && normalBest.saving > bestCash.saving) {
    normalBest.comparison = `검증된 비현금 혜택 ${normalBest.saving.toLocaleString()}원 vs 현금제휴 ${bestCash.saving.toLocaleString()}원 → 비현금 결제가 ${(normalBest.saving - bestCash.saving).toLocaleString()}원 이득`
    return normalBest
  } else if (bestCash && normalBest.saving === bestCash.saving) {
    normalBest.comparison = `검증된 비현금 혜택과 현금제휴가 각각 ${bestCash.saving.toLocaleString()}원으로 동일`
    return normalBest
  }
  return normalBest
}
