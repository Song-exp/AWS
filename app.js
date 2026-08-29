// ═══════════════════════════════════════════════════════════
// 페이픽 + 거지앱 통합 앱 로직
// ═══════════════════════════════════════════════════════════

const CATEGORY_FILTERS = [
  { key: 'all', label: '전체' },
  { key: 'restaurant', label: '음식점' },
  { key: 'cafe', label: '카페' },
  { key: 'convenience', label: '편의점' },
]

// 자동수집 기준: 경희대 중심 — 제휴 매장까지 포함되도록 1.5km
const CENTER = { lat: 37.5943, lng: 127.0537 }
const SEARCH_RADIUS = 1500
const CATEGORY_CODES = { convenience: 'CS2', cafe: 'CE7', restaurant: 'FD6' }

// 매장명 → 혜택 매칭용 표준 브랜드 감지
const BRAND_PATTERNS = [
  ['스타벅스', '스타벅스'], ['투썸', '투썸플레이스'], ['메가', '메가커피'],
  ['컴포즈', '컴포즈커피'], ['빽다방', '빽다방'], ['GS25', 'GS25'], ['GS 25', 'GS25'],
  ['세븐일레븐', '세븐일레븐'], ['7-ELEVEN', '세븐일레븐'], ['이마트24', '이마트24'],
  ['EMART24', '이마트24'], ['BBQ', 'BBQ'], ['맘스터치', '맘스터치'],
  ['한솥', '한솥'], ['김밥천국', '김밥천국'],
  ['할리스', '할리스'], ['이디야', '이디야커피'], ['배스킨', '배스킨라빈스'],
  ['롯데리아', '롯데리아'], ['BHC', 'BHC'], ['더벤티', '더벤티'], ['공차', '공차'],
  ['파리바게뜨', '파리바게뜨'], ['파리크라상', '파리바게뜨'], ['뚜레쥬르', '뚜레쥬르'],
  ['던킨', '던킨'], ['폴 바셋', '폴바셋'], ['폴바셋', '폴바셋'], ['엔제리너스', '엔제리너스'],
  ['이삭토스트', '이삭토스트'], ['CU', 'CU'],
]
function detectBrand(name) {
  const upper = (name || '').toUpperCase()
  for (const [pat, canon] of BRAND_PATTERNS) {
    if (name.includes(pat) || upper.includes(pat.toUpperCase())) return canon
  }
  return ''
}

const BRAND_STYLE = {
  'CU': { color: '#7b2cbf', mark: 'CU' }, 'GS25': { color: '#0879c9', mark: 'GS' },
  '세븐일레븐': { color: '#e31e24', mark: '7' }, '이마트24': { color: '#f5c400', mark: '24' },
  '스타벅스': { color: '#00704a', mark: '★' }, '투썸플레이스': { color: '#c8102e', mark: 'T' },
  '메가커피': { color: '#ffce00', mark: 'M' }, '컴포즈커피': { color: '#1a1a1a', mark: 'C' },
  '빽다방': { color: '#ffdd00', mark: 'B' }, 'BBQ': { color: '#c8102e', mark: 'B' },
  '맘스터치': { color: '#ed1c24', mark: 'M' }, '한솥': { color: '#e60012', mark: '한' },
  '김밥천국': { color: '#e8552d', mark: '김' },
}
const CAT_STYLE = {
  restaurant: { color: '#ef4444', label: '음식점' },
  cafe: { color: '#f97316', label: '카페' },
  convenience: { color: '#eab308', label: '편의점' },
}
function storeStyle(brand, cat) {
  return BRAND_STYLE[brand] || CAT_STYLE[cat] || { color: '#5b5ce2', mark: '' }
}
function categoryColor(category) {
  return CAT_STYLE[category]?.color || '#6b7280'
}

const initialDemoUser = DEMO_USERS[0]
const state = {
  owned: new Set(initialDemoUser.owned),
  active: new Set(initialDemoUser.owned),
  category: 'all',
  sort: 'distance',
  view: 'map',
  page: 'methods',
  mapStarted: false,
  currentUserId: initialDemoUser.id,
  location: { lat: CENTER.lat, lng: CENTER.lng },
  spend: 10000,
  stores: STORES,
  profile: { ...initialDemoUser.profile },
}

// 추천 계산에 넘길 옵션(프로필)
function planOpts() {
  return { profile: state.profile }
}

function getDisplayName(store) {
  return store.name || (store.brand ? `${store.brand} ${store.branch}` : store.branch)
}

// ─── 외부 데이터 소스 로드 (코드 배포 없이 갱신) ───
// 지금은 정적 JSON, 추후 서버 API URL로 교체하면 그대로 실시간 갱신됨.
const BENEFITS_SOURCE = 'benefits.json'
const KHU_ALLIANCE_SOURCE = 'benefits_khu_alliance.json'
const GOODDEAL_SOURCE = 'benefits_gooddeal.json'
const LOCAL_CURRENCY_MERCHANTS_SOURCE = 'local_currency_merchants.json'

let localCurrencyMerchantIndex = { seoulPay: [], onnuriDigital: [] }

function normalizeMerchantName(value) {
  return String(value || '')
    .normalize('NFKC')
    .toLowerCase()
    .replace(/주식회사|㈜|\(주\)/g, '')
    .replace(/메가\s*(?:엠지씨|mgc)\s*커피/g, '메가커피')
    .replace(/비에이치씨|bhc/g, 'bhc')
    .replace(/지에스\s*25|gs\s*25/g, 'gs25')
    .replace(/씨유|cu/g, 'cu')
    .replace(/7\s*-?\s*eleven|세븐\s*일레븐/g, '세븐일레븐')
    .replace(/등촌\s*샤브\s*칼국수/g, '등촌칼국수')
    .replace(/bhcbhc/g, 'bhc')
    .replace(/[^0-9a-z가-힣]/g, '')
}

function addressEvidence(value) {
  const text = String(value || '').normalize('NFKC').toLowerCase()
  const roads = new Set()
  const lots = new Set()
  const dongs = new Set()
  let match

  const roadPattern = /([가-힣0-9]+(?:대로|로|길))\s*(\d+(?:-\d+)?)/g
  while ((match = roadPattern.exec(text))) roads.add(`${match[1]}:${match[2]}`)

  const lotPattern = /([가-힣]+동)\s*(\d+(?:-\d+)?)(?=\s|,|\)|$)(?!\s*(?:호|층))/g
  while ((match = lotPattern.exec(text))) lots.add(`${match[1]}:${match[2]}`)

  const dongPattern = /([가-힣]+동)/g
  while ((match = dongPattern.exec(text))) dongs.add(match[1])

  return { roads, lots, dongs, precise: roads.size > 0 || lots.size > 0 }
}

function setsOverlap(left, right) {
  for (const value of left) if (right.has(value)) return true
  return false
}

function addressMatchType(store, merchant, exactUniqueName = false) {
  const storeAddresses = [store.address, store.roadAddress, store.lotAddress]
    .filter(Boolean)
    .map(addressEvidence)
  const merchantAddress = addressEvidence(merchant.address)

  for (const storeAddress of storeAddresses) {
    if (setsOverlap(storeAddress.roads, merchantAddress.roads)) return 'road-number'
    if (setsOverlap(storeAddress.lots, merchantAddress.lots)) return 'lot-number'
  }

  // 일부 온누리 원본은 번지 없이 동만 기록되어 있다. 이 경우에는
  // 지점까지 포함한 유일한 상호가 완전히 같고 동도 같을 때만 허용한다.
  if (exactUniqueName && !merchantAddress.precise) {
    for (const storeAddress of storeAddresses) {
      if (setsOverlap(storeAddress.dongs, merchantAddress.dongs)) return 'unique-name-and-dong'
    }
  }
  return ''
}

function buildLocalCurrencyIndex(payload) {
  const prepare = rows => {
    const nameCounts = new Map()
    const prepared = rows.map(row => {
      const names = [...new Set([row.name, row.keyword].map(normalizeMerchantName).filter(Boolean))]
      names.forEach(name => nameCounts.set(name, (nameCounts.get(name) || 0) + 1))
      return { ...row, _normalizedNames: names }
    })
    return prepared.map(row => ({
      ...row,
      _uniqueNames: row._normalizedNames.filter(name => nameCounts.get(name) === 1),
    }))
  }

  return {
    seoulPay: prepare(Array.isArray(payload?.seoulPay) ? payload.seoulPay : []),
    // 지류 전용 5곳은 디지털 온누리 후보 인덱스에 처음부터 넣지 않는다.
    onnuriDigital: prepare(Array.isArray(payload?.onnuri)
      ? payload.onnuri.filter(row => row.digital === true)
      : []),
  }
}

function merchantNameMatch(storeName, merchant) {
  const normalizedStore = normalizeMerchantName(storeName)
  if (!normalizedStore) return { matched: false, exactUnique: false }

  let matched = false
  let exactUnique = false
  for (const merchantName of merchant._normalizedNames) {
    const exact = normalizedStore === merchantName
    const strongPartial = Math.min(normalizedStore.length, merchantName.length) >= 4 &&
      (normalizedStore.includes(merchantName) || merchantName.includes(normalizedStore))
    if (exact || strongPartial) matched = true
    if (exact && merchant._uniqueNames.includes(merchantName)) exactUnique = true
  }
  return { matched, exactUnique }
}

function matchLocalCurrencyMerchant(store, merchants) {
  const storeName = getDisplayName(store)
  for (const merchant of merchants) {
    const nameMatch = merchantNameMatch(storeName, merchant)
    if (!nameMatch.matched) continue
    const evidence = addressMatchType(store, merchant, nameMatch.exactUnique)
    if (!evidence) continue
    return { name: merchant.name, address: merchant.address, evidence }
  }
  return null
}

function attachLocalCurrencyFlags(stores) {
  return stores.map(store => {
    const seoulPayMatch = matchLocalCurrencyMerchant(store, localCurrencyMerchantIndex.seoulPay)
    const onnuriMatch = matchLocalCurrencyMerchant(store, localCurrencyMerchantIndex.onnuriDigital)
    return {
      ...store,
      localCurrency: {
        seoulPay: Boolean(seoulPayMatch),
        onnuriDigital: Boolean(onnuriMatch),
        matches: { seoulPay: seoulPayMatch, onnuriDigital: onnuriMatch },
      },
    }
  })
}

// 브라우저 콘솔과 자동 스모크 테스트에서 동일한 매칭 규칙을 검증할 수 있게 한다.
globalThis.PayPickLocalCurrencyMatcher = Object.freeze({
  normalizeMerchantName,
  addressEvidence,
  addressMatchType,
  buildLocalCurrencyIndex,
  matchLocalCurrencyMerchant,
})

async function loadLocalCurrencyMerchants() {
  try {
    const response = await fetch(LOCAL_CURRENCY_MERCHANTS_SOURCE, { cache: 'no-store' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const json = await response.json()
    localCurrencyMerchantIndex = buildLocalCurrencyIndex(json)
    state.localCurrencyUpdatedAt = json.updatedAt || null
    updateDataNote()
  } catch (e) {
    // 가맹점 원본을 못 읽으면 지역화폐는 어느 매장에도 적용하지 않는다.
    localCurrencyMerchantIndex = { seoulPay: [], onnuriDigital: [] }
    console.warn('지역화폐 가맹점 데이터 로드 실패 — 지역화폐 혜택 비활성', e)
  }
}

async function loadBenefits() {
  try {
    const [mainRes, khuRes, gooddealRes] = await Promise.all([
      fetch(BENEFITS_SOURCE, { cache: 'no-store' }),
      fetch(KHU_ALLIANCE_SOURCE, { cache: 'no-store' }),
      fetch(GOODDEAL_SOURCE, { cache: 'no-store' }),
    ])

    if (mainRes.ok) {
      const json = await mainRes.json()
      if (json && Array.isArray(json.benefits)) {
        let all = json.benefits
        const sourceDates = [json.updatedAt]

        // 팀 CSV에서 변환한 카카오페이 굿딜 전체 목록이 있으면
        // benefits.json의 일부 수기 목록(gd_*)을 대체해 중복을 막는다.
        if (gooddealRes.ok) {
          const gooddeal = await gooddealRes.json()
          if (gooddeal && Array.isArray(gooddeal.benefits)) {
            all = all.filter(b => !b.id.startsWith('gd_')).concat(gooddeal.benefits)
            sourceDates.push(gooddeal.updatedAt)
          }
        }

        // 경영대 제휴 데이터 병합
        if (khuRes.ok) {
          const khu = await khuRes.json()
          if (khu && Array.isArray(khu.benefits)) {
            all = all.concat(khu.benefits)
            sourceDates.push(khu.updatedAt)
          }
        }
        setBenefits(all)
        state.benefitsUpdatedAt = sourceDates.filter(Boolean).sort().at(-1) || null
        updateDataNote()
      }
    }
  } catch (e) {
    console.warn('혜택 데이터 로드 실패 — 내장 시드 데이터 사용', e)
  }
}

function updateDataNote() {
  const el = document.querySelector('.notice')
  if (!el) return
  const dates = [state.benefitsUpdatedAt, state.localCurrencyUpdatedAt].filter(Boolean)
  if (dates.length) {
    el.textContent = `혜택·가맹점 데이터 기준일 ${dates.sort().at(-1)} · 검증 완료된 혜택만 추천 금액에 반영하고, 미검증 정보는 참고로 분리합니다.`
  }
}

// ─── 카카오 장소검색으로 매장 자동수집 ───
function loadStores(done) {
  const k = window.kakao
  if (!(k && k.maps && k.maps.services)) {
    state.stores = attachLocalCurrencyFlags(STORES)
    done && done()
    return
  }
  const ps = new k.maps.services.Places()
  const center = new k.maps.LatLng(CENTER.lat, CENTER.lng)
  const collected = []
  let pending = 0
  let dispatched = false

  function finalize() {
    if (pending !== 0 || !dispatched) return
    const seen = new Set()
    const uniq = []
    // 정적 제휴 매장 먼저 넣기 (id가 khu_로 시작하는 매장)
    STORES.filter(s => s.id && s.id.startsWith('khu_')).forEach(s => { seen.add(s.id); uniq.push(s) })
    // 자동수집 매장 추가 (중복 제거)
    collected.forEach(s => { if (!seen.has(s.id)) { seen.add(s.id); uniq.push(s) } })
    state.stores = attachLocalCurrencyFlags(uniq.length ? uniq : STORES)
    done && done()
  }

  function mapPlace(p, cat) {
    const name = p.place_name
    const brand = detectBrand(name)
    const style = storeStyle(brand, cat)
    return {
      id: p.id,
      name,
      branch: name,
      brand,
      category: cat,
      address: p.road_address_name || p.address_name || '',
      roadAddress: p.road_address_name || '',
      lotAddress: p.address_name || '',
      lat: parseFloat(p.y),
      lng: parseFloat(p.x),
      color: style.color,
      mark: style.mark,
    }
  }

  Object.entries(CATEGORY_CODES).forEach(([cat, code]) => {
    function fetchPage(page) {
      pending++
      ps.categorySearch(code, (data, status, pagination) => {
        pending--
        if (status === k.maps.services.Status.OK) {
          data.forEach(p => collected.push(mapPlace(p, cat)))
          if (pagination && pagination.hasNextPage && page < 3) {
            fetchPage(page + 1)
          }
        }
        finalize()
      }, { location: center, radius: SEARCH_RADIUS, page })
    }
    fetchPage(1)
  })
  dispatched = true
  finalize()
}

// ─── DOM refs ───
const onboarding = document.querySelector('#onboarding')
const appMain = document.querySelector('#appMain')
const onboardingGroups = document.querySelector('#onboardingGroups')
const categoryFilterRoot = document.querySelector('#categoryFilters')
const methodFilterRoot = document.querySelector('#methodFilters')
const list = document.querySelector('#benefitList')
const emptyState = document.querySelector('#emptyState')
const mapView = document.querySelector('#mapView')
const mapStoreCard = document.querySelector('#mapStoreCard')
const myMethodsChip = document.querySelector('#myMethodsChip')

const demoUserSelect = document.querySelector('#demoUserSelect')
const demoUserSummary = document.querySelector('#demoUserSummary')

let map
let storeOverlays = []
let locationOverlay
let selectedMarker

function showPage(page) {
  state.page = page
  onboarding.hidden = page !== 'methods'
  appMain.hidden = page !== 'map'
  document.body.dataset.page = page
}

function syncDemoUserSummary() {
  const user = DEMO_USERS.find(item => item.id === state.currentUserId)
  if (!user) return
  demoUserSelect.value = user.id
  demoUserSummary.textContent = `보유 카드: ${user.cardLabel}`
  myMethodsChip.textContent = `내 수단 ${state.owned.size}개`
}

function applyDemoUser(userId) {
  const user = DEMO_USERS.find(item => item.id === userId)
  if (!user) return
  state.currentUserId = user.id
  state.owned = new Set(user.owned)
  state.active = new Set(user.owned)
  state.profile = { ...user.profile }
  buildOnboarding()
  buildMethodFilters()
  updateSubmitLabel()
  syncDemoUserSummary()
  if (state.mapStarted) render()
}

function buildDemoUserSelect() {
  demoUserSelect.replaceChildren(...DEMO_USERS.map(user => {
    const option = document.createElement('option')
    option.value = user.id
    option.textContent = `${user.name} · ${user.cardLabel}`
    return option
  }))
  demoUserSelect.addEventListener('change', event => applyDemoUser(event.target.value))
  syncDemoUserSummary()
}

// ═══════════════════════════════════════════
// 온보딩
// ═══════════════════════════════════════════
function buildOnboarding() {
  onboardingGroups.innerHTML = ''
  PAYMENT_GROUPS.forEach(group => {
    const section = document.createElement('section')
    section.className = 'ob-group'

    const h = document.createElement('h3')
    h.textContent = group.label
    section.append(h)

    // 카드는 발급사별로 하위 그룹
    if (group.category === 'card') {
      const roadmap = document.createElement('div')
      roadmap.className = 'mydata-roadmap'
      roadmap.innerHTML = `<span>추가 구현 예정</span><strong>카드 마이데이터 연동</strong><p>보유 카드를 자동으로 불러와 직접 선택 단계를 줄일 예정입니다.</p>`
      section.append(roadmap)

      const byIssuer = {}
      group.methods.forEach(m => {
        (byIssuer[m.issuer] = byIssuer[m.issuer] || []).push(m)
      })
      Object.entries(byIssuer).forEach(([issuer, methods]) => {
        const sub = document.createElement('div')
        sub.className = 'ob-issuer'
        sub.innerHTML = `<span class="ob-issuer-label">${issuer}</span>`
        const grid = document.createElement('div')
        grid.className = 'ob-grid'
        methods.forEach(m => grid.append(makeChip(m)))
        sub.append(grid)
        section.append(sub)
      })
    } else {
      const grid = document.createElement('div')
      grid.className = 'ob-grid'
      group.methods.forEach(m => {
        const chip = makeChip(m)
        if (group.category === 'telecom') chip.textContent = `${m.issuer} ${m.name}`
        grid.append(chip)
      })
      section.append(grid)
    }
    onboardingGroups.append(section)
  })

  buildProfileSection()
}

// 멤버십/등급 프로필 (네이버플러스 여부, 통신사 등급)
function buildProfileSection() {
  const section = document.createElement('section')
  section.className = 'ob-group ob-profile'
  section.innerHTML = `<h3>멤버십 / 등급 <small>(선택 · 혜택 정확도 개선)</small></h3>`

  // 네이버플러스 멤버십
  const naverRow = document.createElement('div')
  naverRow.className = 'ob-profile-row'
  naverRow.innerHTML = `<span class="ob-profile-label">네이버플러스 멤버십</span>`
  const naverBtn = document.createElement('button')
  naverBtn.type = 'button'
  naverBtn.className = 'ob-chip'
  naverBtn.textContent = '가입함'
  naverBtn.setAttribute('aria-pressed', String(state.profile.naverPlus))
  naverBtn.addEventListener('click', () => {
    state.profile.naverPlus = !state.profile.naverPlus
    naverBtn.setAttribute('aria-pressed', String(state.profile.naverPlus))
  })
  naverRow.append(naverBtn)
  section.append(naverRow)

  // 카카오페이 플러스(멤버십)
  const kakaoRow = document.createElement('div')
  kakaoRow.className = 'ob-profile-row'
  kakaoRow.innerHTML = `<span class="ob-profile-label">카카오페이 플러스</span>`
  const kakaoBtn = document.createElement('button')
  kakaoBtn.type = 'button'
  kakaoBtn.className = 'ob-chip'
  kakaoBtn.textContent = '가입함'
  kakaoBtn.setAttribute('aria-pressed', String(state.profile.kakaoPlus))
  kakaoBtn.addEventListener('click', () => {
    state.profile.kakaoPlus = !state.profile.kakaoPlus
    kakaoBtn.setAttribute('aria-pressed', String(state.profile.kakaoPlus))
  })
  kakaoRow.append(kakaoBtn)
  section.append(kakaoRow)

  // 통신사 등급 (VVIP·VIP·Gold = 상위 10% / Silver·일반 = 하위 5%)
  const gradeRow = document.createElement('div')
  gradeRow.className = 'ob-profile-row'
  gradeRow.innerHTML = `<span class="ob-profile-label">통신사 등급</span>`
  // tier: 'vip'(상위 10%) | 'normal'(하위 5%)
  const grades = [
    { label: 'VVIP', tier: 'vip' },
    { label: 'VIP', tier: 'vip' },
    { label: 'Gold', tier: 'vip' },
    { label: 'Silver', tier: 'normal' },
    { label: '일반', tier: 'normal' },
  ]
  if (!state.profile.gradeLabel) state.profile.gradeLabel = 'VIP'
  grades.forEach(g => {
    const b = document.createElement('button')
    b.type = 'button'
    b.className = 'ob-chip'
    b.textContent = g.label
    b.setAttribute('aria-pressed', String(state.profile.gradeLabel === g.label))
    b.addEventListener('click', () => {
      state.profile.gradeLabel = g.label
      state.profile.telecomGrade = g.tier
      gradeRow.querySelectorAll('.ob-chip').forEach(x =>
        x.setAttribute('aria-pressed', String(x.textContent === g.label)))
    })
    gradeRow.append(b)
  })
  section.append(gradeRow)
  const hint = document.createElement('p')
  hint.className = 'ob-grade-hint'
  hint.textContent = 'VVIP·VIP·Gold는 상위(약 10%), Silver·일반은 하위(약 5%) 혜택이 적용돼요.'
  section.append(hint)

  onboardingGroups.append(section)
}

function makeChip(method) {
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'ob-chip'
  btn.dataset.method = method.id
  btn.textContent = method.name
  btn.setAttribute('aria-pressed', String(state.owned.has(method.id)))
  btn.addEventListener('click', () => {
    if (state.owned.has(method.id)) {
      state.owned.delete(method.id)
      btn.setAttribute('aria-pressed', 'false')
    } else {
      state.owned.add(method.id)
      btn.setAttribute('aria-pressed', 'true')
    }
    updateSubmitLabel()
  })
  return btn
}

function updateSubmitLabel() {
  const btn = document.querySelector('#onboardingSubmit')
  btn.textContent = state.owned.size > 0
    ? `${state.owned.size}개 선택 완료 · 할인 지도 보기`
    : '카드·혜택 수단을 선택하세요'
}

document.querySelector('#onboardingSubmit').addEventListener('click', () => {
  if (state.owned.size === 0) {
    alert('결제수단을 최소 1개 이상 선택해주세요.')
    return
  }
  state.active = new Set(state.owned)
  buildMethodFilters()
  syncDemoUserSummary()
  showPage('map')
  if (!state.mapStarted) {
    state.mapStarted = true
    startMap()
  } else {
    render()
    setView(state.view)
  }
})

document.querySelector('#editMethodsButton').addEventListener('click', () => showPage('methods'))

// ═══════════════════════════════════════════
// 업종 필터
// ═══════════════════════════════════════════
function buildCategoryFilters() {
  categoryFilterRoot.innerHTML = ''
  CATEGORY_FILTERS.forEach(f => {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'pay-filter'
    btn.dataset.category = f.key
    btn.setAttribute('aria-pressed', String(state.category === f.key))
    btn.textContent = f.label
    btn.addEventListener('click', () => {
      state.category = f.key
      document.querySelectorAll('#categoryFilters .pay-filter').forEach(b =>
        b.setAttribute('aria-pressed', String(b.dataset.category === f.key)))
      render()
    })
    categoryFilterRoot.append(btn)
  })
}

myMethodsChip.addEventListener('click', () => showPage('methods'))

// ─── 보유 결제수단 필터 (메인 화면) ───
function buildMethodFilters() {
  methodFilterRoot.innerHTML = ''
  // 온보딩에서 고른 수단만, 카테고리 순서대로 노출
  PAYMENT_GROUPS.forEach(group => {
    group.methods.forEach(m => {
      if (!state.owned.has(m.id)) return
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'pay-filter method-filter'
      btn.dataset.method = m.id
      btn.setAttribute('aria-pressed', String(state.active.has(m.id)))
      const label = group.category === 'telecom' ? `${m.issuer} ${m.name}` : m.name
      btn.textContent = label
      btn.addEventListener('click', () => {
        if (state.active.has(m.id)) state.active.delete(m.id)
        else state.active.add(m.id)
        btn.setAttribute('aria-pressed', String(state.active.has(m.id)))
        render()
      })
      methodFilterRoot.append(btn)
    })
  })
}

document.querySelector('#methodAllButton').addEventListener('click', () => {
  state.active = new Set(state.owned)
  document.querySelectorAll('#methodFilters .method-filter').forEach(b =>
    b.setAttribute('aria-pressed', 'true'))
  render()
})

// ═══════════════════════════════════════════
// 지도
// ═══════════════════════════════════════════
function distanceKm(a, b) {
  const rad = v => v * Math.PI / 180
  const dLat = rad(b.lat - a.lat)
  const dLng = rad(b.lng - a.lng)
  const v = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2
  return 6371 * 2 * Math.atan2(Math.sqrt(v), Math.sqrt(1 - v))
}

function formatDistance(km) {
  return km < 1 ? `${Math.max(10, Math.round(km * 1000 / 10) * 10)}m` : `${km.toFixed(1)}km`
}

function fitServiceArea() {
  const bounds = new kakao.maps.LatLngBounds()
  bounds.extend(new kakao.maps.LatLng(37.5880, 127.0480))
  bounds.extend(new kakao.maps.LatLng(37.5980, 127.0640))
  map.setBounds(bounds, 50, 50, 50, 50)
}

function initMap() {
  const center = new kakao.maps.LatLng(37.5930, 127.0555)
  map = new kakao.maps.Map(document.querySelector('#map'), { center, level: 4 })
  map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT)
  document.querySelector('#recenterButton').addEventListener('click', fitServiceArea)
  fitServiceArea()
}

// 업종색 스팟 + 할인액만 표시하는 지도 마커
function categoryMarker(store, plan) {
  const saving = plan?.saving || 0
  const amount = saving > 0 ? `-${saving.toLocaleString()}원` : '혜택 확인'
  return `<span class="discount-marker" style="--category-color:${categoryColor(store.category)}">
    <span class="category-spot" aria-hidden="true"></span>
    <strong>${amount}</strong>
  </span>`
}

function storeDetails(store, plan, recs, references = []) {
  const name = getDisplayName(store)
  const catLabel = CATEGORY_FILTERS.find(c => c.key === store.category)?.label || ''

  let body = ''
  if (plan && plan.saving > 0) {
    const partRows = plan.benefits.map(r =>
      `<div class="map-popup-offer">
        <span>${r.method.issuer} ${r.method.name}</span>
        <strong>${r.label}</strong>
      </div>
      <p class="map-popup-condition">${r.benefit.cond || ''} · 출처: ${r.benefit.evidence || '미기재'}</p>`).join('')
    const header = `<div class="map-popup-best">
        ${plan.combo ? '검증된 최적 조합' : plan.cashRestricted ? '검증된 현금 혜택' : '검증된 최적 혜택'} <b>-${plan.saving.toLocaleString()}원</b>
        <span class="popup-spend">1만원 결제 기준</span>
      </div>`
    body = header + (plan.comparison ? `<p class="comparison-note">${plan.comparison}</p>` : '') + partRows
  } else {
    body = '<div class="map-popup-offer"><span>검증 완료된 금액 혜택 없음</span></div>'
  }

  if (references.length) {
    body += `<div class="reference-benefits">
      <b>확인 필요 · 금액 계산 제외</b>
      ${references.slice(0, 3).map(r => `<p>${r.method.issuer} ${r.method.name}: ${r.label}<br><small>${r.referenceReason} · ${r.benefit.cond || ''}</small></p>`).join('')}
    </div>`
  }

  return `<div class="map-popup">
    <p class="map-popup-brand">${catLabel}</p>
    <h3>${name}</h3>
    <span class="map-popup-address">${store.address}</span>
    ${body}
  </div>`
}

function selectStore(element, details) {
  selectedMarker?.classList.remove('is-selected')
  selectedMarker = element
  element.classList.add('is-selected')
  mapStoreCard.innerHTML = `${details}<button type="button" aria-label="상세 닫기">×</button>`
  mapStoreCard.hidden = false
  mapStoreCard.querySelector('button').addEventListener('click', () => {
    mapStoreCard.hidden = true
    element.classList.remove('is-selected')
    selectedMarker = null
  })
}

function visibleStores() {
  return state.stores.filter(s => {
    if (state.category !== 'all' && s.category !== state.category) return false
    return storeHasBenefit(s, state.active, state.profile)
  })
}

function updateMap() {
  if (!map) return
  storeOverlays.forEach(o => o.setMap(null))
  storeOverlays = []
  locationOverlay?.setMap(null)
  selectedMarker = null
  mapStoreCard.hidden = true

  visibleStores().forEach(store => {
    const recs = getRecommendations(store, state.active, state.spend, planOpts())
    const references = getReferenceRecommendations(store, state.active, state.spend, planOpts())
    const plan = computeBestPlan(store, state.active, state.spend, planOpts())
    const details = storeDetails(store, plan, recs, references)
    const el = document.createElement('button')
    el.type = 'button'
    el.className = 'store-icon'
    const name = getDisplayName(store)
    const catLabel = CATEGORY_FILTERS.find(item => item.key === store.category)?.label || ''
    const savingLabel = plan.saving > 0 ? `${plan.saving.toLocaleString()}원 할인` : '혜택 금액 확인 필요'
    el.setAttribute('aria-label', `${name}, ${catLabel}, ${savingLabel}`)
    el.innerHTML = `
      <span class="store-marker">${categoryMarker(store, plan)}</span>
      <span class="marker-hover">${details}</span>`
    const overlay = new kakao.maps.CustomOverlay({
      map,
      position: new kakao.maps.LatLng(store.lat, store.lng),
      content: el,
      yAnchor: 0.5,
      zIndex: 3,
    })
    el.addEventListener('mouseenter', () => overlay.setZIndex(1000))
    el.addEventListener('mouseleave', () => overlay.setZIndex(el.classList.contains('is-selected') ? 900 : 3))
    el.addEventListener('click', e => {
      e.stopPropagation()
      overlay.setZIndex(900)
      selectStore(el, details)
    })
    storeOverlays.push(overlay)
  })

  const locEl = document.createElement('span')
  locEl.className = 'current-location'
  locEl.title = '기준 위치'
  locationOverlay = new kakao.maps.CustomOverlay({
    map,
    position: new kakao.maps.LatLng(state.location.lat, state.location.lng),
    content: locEl,
    zIndex: 2,
  })
}

// ═══════════════════════════════════════════
// 리스트 렌더
// ═══════════════════════════════════════════
function render() {
  const stores = visibleStores().map(store => {
    const recs = getRecommendations(store, state.active, state.spend, planOpts())
    const references = getReferenceRecommendations(store, state.active, state.spend, planOpts())
    const plan = computeBestPlan(store, state.active, state.spend, planOpts())
    return { store, recs, references, plan, distance: distanceKm(state.location, store) }
  })

  stores.sort(state.sort === 'discount'
    ? (a, b) => (b.plan?.saving || 0) - (a.plan?.saving || 0) || a.distance - b.distance
    : (a, b) => a.distance - b.distance || (b.plan?.saving || 0) - (a.plan?.saving || 0))

  list.replaceChildren()
  stores.forEach(({ store, recs, references, plan, distance }) => {
    const card = document.createElement('article')
    card.className = 'benefit-card'
    const name = getDisplayName(store)
    const catLabel = CATEGORY_FILTERS.find(c => c.key === store.category)?.label || ''

    // 조합 구성요소
    const planIds = new Set(plan.benefits.map(r => r.benefit.id))
    const partRows = plan.benefits.map(r =>
      `<li class="plan-benefit-detail">
        <span>${r.method.issuer} ${r.method.name}<small>${r.benefit.cond || ''}</small></span>
        <em>${r.label} <i class="verify-tag mini ok">검증</i></em>
      </li>`).join('')
    // 조합에 안 쓰인 검증 완료 옵션
    const others = recs.filter(r => !planIds.has(r.benefit.id)).slice(0, 2).map(r =>
      `<li class="alt"><span>${r.method.issuer} ${r.method.name}</span><em>${r.label}</em></li>`).join('')
    // 공식 근거 또는 적용 전제조건이 부족해 계산에서 제외한 참고 혜택
    const referenceRows = references.slice(0, 3).map(r =>
      `<li class="reference-rec">
        <span>${r.method.issuer} ${r.method.name}<small>${r.referenceReason} · ${r.benefit.cond || ''}</small></span>
        <em>${r.label} <i class="verify-tag mini">계산 제외</i></em>
      </li>`).join('')

    card.style.setProperty('--category-color', categoryColor(store.category))
    card.innerHTML = `
      <div class="card-content">
        <div class="card-topline">
          <span class="store-name"><i class="category-dot" aria-hidden="true"></i>${name}</span>
          <span class="distance">${formatDistance(distance)}</span>
        </div>
        <p class="address">${catLabel} · ${store.address}</p>
        ${plan.saving > 0 ? `
          <div class="offer-row">
            <span class="pay-badge best-pay">${plan.combo ? '검증된 최적 조합' : plan.cashRestricted ? '검증된 현금 혜택' : '검증된 최적 혜택'}</span>
            <p><strong class="discount">-${plan.saving.toLocaleString()}원</strong></p>
          </div>
          ${plan.comparison ? `<p class="comparison-note">${plan.comparison}</p>` : ''}
          <ul class="plan-parts">${partRows}</ul>
          ${others ? `<p class="alt-label">다른 검증 옵션</p><ul class="other-recs">${others}</ul>` : ''}
        ` : `<p class="condition">검증 완료된 금액 혜택 없음</p>`}
        ${referenceRows ? `<p class="alt-label reference-label">확인 필요 · 추천 금액 계산에서 제외</p><ul class="other-recs reference-recs">${referenceRows}</ul>` : ''}
      </div>`
    list.append(card)
  })

  document.querySelector('#resultCount').textContent = stores.length
  emptyState.hidden = stores.length > 0
  updateMap()
}

// ═══════════════════════════════════════════
// 뷰 전환
// ═══════════════════════════════════════════
function setView(view) {
  state.view = view
  const showMap = view === 'map'
  mapView.hidden = !showMap
  list.hidden = showMap
  document.querySelector('.sort-label').hidden = showMap
  document.querySelectorAll('.view-button').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.view === view)))
  if (showMap && map) setTimeout(() => map.relayout(), 0)
}

document.querySelector('.view-toggle').addEventListener('click', e => {
  const btn = e.target.closest('.view-button')
  if (btn) setView(btn.dataset.view)
})

document.querySelector('#sortSelect').addEventListener('change', e => {
  state.sort = e.target.value
  render()
})

emptyState.querySelector('button').addEventListener('click', () => showPage('methods'))

// ═══════════════════════════════════════════
// 지도 시작
// ═══════════════════════════════════════════
function startMap() {
  buildCategoryFilters()
  if (window.kakao?.maps) {
    kakao.maps.load(async () => {
      if (!map) initMap()
      await Promise.all([loadBenefits(), loadLocalCurrencyMerchants()])
      state.stores = attachLocalCurrencyFlags(STORES)
      render()              // 정적 매장 + 최신 혜택/가맹점으로 렌더
      setView('map')
      loadStores(render)    // 자동수집 완료되면 실제 매장으로 교체 렌더
    })
    return
  }
  document.querySelector('#map').innerHTML =
    '<p class="map-error">카카오맵을 불러오지 못했어요.<br>config.js의 JavaScript 키와 허용 도메인을 확인해 주세요.</p>'
  Promise.all([loadBenefits(), loadLocalCurrencyMerchants()]).then(() => {
    state.stores = attachLocalCurrencyFlags(STORES)
    setView('list')
    render()
  })
}

// 초기화
buildDemoUserSelect()
buildOnboarding()
buildMethodFilters()
updateSubmitLabel()
showPage('methods')
