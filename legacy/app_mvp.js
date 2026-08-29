// ═══════════════════════════════════════════════════════════
// 페이픽 + 거지앱 통합 앱 로직
// ═══════════════════════════════════════════════════════════

const CATEGORY_FILTERS = [
  { key: 'all', label: '전체', icon: '⌂' },
  { key: 'restaurant', label: '음식점', icon: '🍚' },
  { key: 'cafe', label: '카페', icon: '☕' },
  { key: 'convenience', label: '편의점', icon: '🛒' },
  { key: 'culture', label: '영화·문화', icon: '🎬' },
  { key: 'campus', label: '학교 제휴', icon: '🎓' },
  { key: 'lifestyle', label: '생활편의', icon: '✨' },
]

// 자동수집 기준: 경희대 중심 — 제휴 매장까지 포함되도록 1.5km
const CENTER = { lat: 37.5943, lng: 127.0537 }
const SEARCH_RADIUS = 1500
const CATEGORY_CODES = { convenience: 'CS2', cafe: 'CE7', restaurant: 'FD6' }

// 매장명 → 혜택 매칭용 표준 브랜드 감지
const BRAND_PATTERNS = [
  ['스타벅스', '스타벅스'], ['투썸', '투썸플레이스'], ['메가커피', '메가커피'], ['메가MGC', '메가커피'],
  ['컴포즈', '컴포즈커피'], ['빽다방', '빽다방'], ['GS25', 'GS25'], ['GS 25', 'GS25'],
  ['세븐일레븐', '세븐일레븐'], ['7-ELEVEN', '세븐일레븐'], ['이마트에브리데이', '이마트에브리데이'],
  ['이마트24', '이마트24'], ['EMART24', '이마트24'], ['CGV', 'CGV'], ['메가박스', '메가박스'],
  ['롯데시네마', '롯데시네마'], ['다이소', '다이소'], ['올리브영', '올리브영'],
  ['BBQ', 'BBQ'], ['맘스터치', '맘스터치'], ['한솥', '한솥'], ['김밥천국', '김밥천국'],
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
  '이마트에브리데이': { color: '#f59e0b', mark: 'E' },
  'CGV': { color: '#f97316', mark: 'C' }, '메가박스': { color: '#351f66', mark: 'M' },
  '롯데시네마': { color: '#e60012', mark: 'L' }, '다이소': { color: '#e6002d', mark: 'D' },
  '올리브영': { color: '#84bd00', mark: 'O' },
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
  culture: { color: '#e11d48', label: '영화·문화' },
  campus: { color: '#4f46e5', label: '학교 제휴' },
  lifestyle: { color: '#0ea5e9', label: '생활편의' },
}
function storeStyle(brand, cat) {
  return BRAND_STYLE[brand] || CAT_STYLE[cat] || { color: '#5b5ce2', mark: '' }
}
function categoryColor(category) {
  return CAT_STYLE[category]?.color || '#6b7280'
}

const EMPTY_PROFILE = { naverPlus: false, kakaoPlus: false, telecomGrade: 'vip', gradeLabel: 'VIP' }
const state = {
  owned: new Set(),
  active: new Set(),
  autoImported: new Set(),
  category: 'all',
  sort: 'personalized',
  view: 'map',
  page: 'methods',
  mapStarted: false,
  currentUserId: '',
  isConnecting: false,
  connectionRequest: 0,
  location: { lat: CENTER.lat, lng: CENTER.lng },
  spend: 10000,
  stores: STORES,
  profile: { ...EMPTY_PROFILE },
  preferences: [],
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
const FACILITIES_SOURCE = 'benefits_facilities.json'
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
    const [mainRes, khuRes, facilitiesRes, gooddealRes] = await Promise.all([
      fetch(BENEFITS_SOURCE, { cache: 'no-store' }),
      fetch(KHU_ALLIANCE_SOURCE, { cache: 'no-store' }),
      fetch(FACILITIES_SOURCE, { cache: 'no-store' }),
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

        // 비식음료 편의시설 참고 혜택 병합
        if (facilitiesRes.ok) {
          const facilities = await facilitiesRes.json()
          if (facilities && Array.isArray(facilities.benefits)) {
            all = all.concat(facilities.benefits)
            sourceDates.push(facilities.updatedAt)
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
    // 정적 제휴·편의시설은 자동수집 결과와 무관하게 항상 유지한다.
    STORES.filter(s => s.id && (s.id.startsWith('khu_') || s.id.startsWith('facility_')))
      .forEach(s => { seen.add(s.id); uniq.push(s) })
    const placeKey = store => store.category === 'culture'
      ? `${store.category}:${store.brand}:${store.lat.toFixed(3)}:${store.lng.toFixed(3)}`
      : `${getDisplayName(store)}:${store.lat.toFixed(3)}:${store.lng.toFixed(3)}`
    // 자동수집 매장 추가 (영화관은 브랜드·좌표, 그 외는 이름·좌표 기준 중복 제거)
    const placeKeys = new Set(uniq.map(placeKey))
    collected.forEach(s => {
      const key = placeKey(s)
      if (!seen.has(s.id) && !placeKeys.has(key)) {
        seen.add(s.id)
        placeKeys.add(key)
        uniq.push(s)
      }
    })
    state.stores = attachLocalCurrencyFlags(uniq.length ? uniq : STORES)
    done && done()
  }

  function mapPlace(p, cat, brandHint = '') {
    const name = p.place_name
    const brand = brandHint || detectBrand(name)
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

  // 문화 카테고리는 서울 전역의 실제 영화관 지점만 브랜드별로 수집한다.
  ;['CGV', '메가박스', '롯데시네마'].forEach(brand => {
    function fetchCinemaPage(page) {
      pending++
      ps.keywordSearch(`서울 ${brand}`, (data, status, pagination) => {
        pending--
        if (status === k.maps.services.Status.OK) {
          data
            .filter(place => {
              const address = place.address_name || place.road_address_name || ''
              const name = place.place_name || ''
              const category = place.category_name || ''
              return address.startsWith('서울') && name.startsWith(brand) &&
                !/주차장|전기차|충전소|본사|노래|포토|은행|피트니스|투루카|쏘카|G car/i.test(name) &&
                (category.includes('영화관') || category.includes('문화'))
            })
            .forEach(place => collected.push(mapPlace(place, 'culture', brand)))
          if (pagination && pagination.hasNextPage && page < 3) fetchCinemaPage(page + 1)
        }
        finalize()
      }, { page })
    }
    fetchCinemaPage(1)
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
const personalRecommendation = document.querySelector('#personalRecommendation')

const demoUserSelect = document.querySelector('#demoUserSelect')
const onboardingUserSelect = document.querySelector('#onboardingUserSelect')
const demoUserSummary = document.querySelector('#demoUserSummary')
const myDataStatus = document.querySelector('#myDataStatus')

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
  demoUserSelect.value = user?.id || ''
  onboardingUserSelect.value = user?.id || ''
  myMethodsChip.textContent = `내 수단 ${state.owned.size}개`

  if (!user) {
    demoUserSummary.textContent = '사용자 미선택'
    personalRecommendation.innerHTML = '<span>직접 설정</span><strong>내 결제수단</strong><p>선택한 수단을 기준으로 주변 혜택을 계산합니다.</p>'
    return
  }

  const preferenceLabels = state.preferences
    .map(key => CATEGORY_FILTERS.find(item => item.key === key)?.label)
    .filter(Boolean)
  demoUserSummary.textContent = `대표 카드: ${user.cardLabel}`
  personalRecommendation.innerHTML = `<span>맞춤 추천</span><strong>${user.name}</strong><p>${preferenceLabels.join(' · ')} 선호와 보유수단 ${state.owned.size}개를 반영해 순위를 다시 계산했어요.</p>`
}

function methodNames(methodIds) {
  return [...methodIds]
    .map(id => PAYMENT_METHODS[id])
    .filter(Boolean)
    .map(method => method.name)
}

function setMyDataStatus(mode, user) {
  myDataStatus.className = `mydata-status is-${mode}`
  if (mode === 'connecting') {
    myDataStatus.innerHTML = '<span class="mydata-spinner" aria-hidden="true"></span><p><strong>마이데이터 연결 중</strong><br>계좌·카드·페이 정보를 안전하게 불러오고 있어요.</p>'
  } else if (mode === 'connected' && user) {
    const names = methodNames(state.autoImported)
    myDataStatus.innerHTML = `<span class="mydata-status-icon" aria-hidden="true">✓</span><p><strong>${user.name} 연결 완료 · ${names.length}개</strong><br>${names.join(' · ')}<small>아래에서 연결 수단을 삭제하거나 다른 수단을 직접 추가할 수 있어요.</small></p>`
  } else {
    myDataStatus.innerHTML = '<span class="mydata-status-icon" aria-hidden="true"></span><p>아직 연결된 정보가 없습니다. 사용자를 선택하거나 아래에서 직접 수단을 추가하세요.</p>'
  }
}

function applyDemoUser(userId) {
  const user = DEMO_USERS.find(item => item.id === userId)
  const request = ++state.connectionRequest

  if (!user) {
    state.currentUserId = ''
    state.isConnecting = false
    state.owned = new Set()
    state.active = new Set()
    state.autoImported = new Set()
    state.profile = { ...EMPTY_PROFILE }
    state.preferences = []
    setMyDataStatus('empty')
    buildOnboarding()
    buildMethodFilters()
    buildCategoryFilters()
    updateSubmitLabel()
    syncDemoUserSummary()
    if (state.mapStarted) render()
    return
  }

  state.currentUserId = user.id
  state.isConnecting = true
  state.owned = new Set()
  state.active = new Set()
  state.autoImported = new Set()
  demoUserSelect.value = user.id
  onboardingUserSelect.value = user.id
  setMyDataStatus('connecting', user)
  buildOnboarding()
  updateSubmitLabel()

  window.setTimeout(() => {
    if (request !== state.connectionRequest) return
    state.isConnecting = false
    state.owned = new Set(user.owned)
    state.active = new Set(user.owned)
    state.autoImported = new Set(user.owned)
    state.profile = { ...user.profile }
    state.preferences = [...user.preferences]
    state.category = 'all'
    state.sort = 'personalized'
    document.querySelector('#sortSelect').value = state.sort
    setMyDataStatus('connected', user)
    buildOnboarding()
    buildMethodFilters()
    buildCategoryFilters()
    updateSubmitLabel()
    syncDemoUserSummary()
    if (state.mapStarted) render()
  }, 700)
}

function userOptions() {
  const placeholder = document.createElement('option')
  placeholder.value = ''
  placeholder.textContent = '사용자를 선택하세요'
  return [placeholder, ...DEMO_USERS.map(user => {
    const option = document.createElement('option')
    option.value = user.id
    option.textContent = `${user.name} · ${user.cardLabel}`
    return option
  })]
}

function buildDemoUserSelect() {
  demoUserSelect.replaceChildren(...userOptions())
  onboardingUserSelect.replaceChildren(...userOptions())
  demoUserSelect.addEventListener('change', event => applyDemoUser(event.target.value))
  onboardingUserSelect.addEventListener('change', event => applyDemoUser(event.target.value))
  setMyDataStatus('empty')
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

    // 마이데이터에서 불러온 카드와 직접 추가 가능한 카드를 함께 표시
    if (group.category === 'card') {
      const roadmap = document.createElement('div')
      roadmap.className = 'mydata-roadmap'
      roadmap.innerHTML = `<span>${state.currentUserId ? '연결됨' : '직접 선택 가능'}</span><strong>카드 마이데이터</strong><p>${state.currentUserId ? '자동으로 불러온 카드가 선택되어 있습니다. 다른 카드를 추가하거나 삭제할 수 있어요.' : '시연 사용자를 선택하면 연결 카드를 자동으로 불러옵니다. 기다리지 않고 직접 선택해도 됩니다.'}</p>`
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
        if (group.category === 'telecom') chip.querySelector('span').textContent = `${m.issuer} ${m.name}`
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
  btn.disabled = state.isConnecting
  btn.setAttribute('aria-pressed', String(state.owned.has(method.id)))

  const renderChip = () => {
    const imported = state.autoImported.has(method.id) && state.owned.has(method.id)
    btn.classList.toggle('is-imported', imported)
    btn.classList.toggle('is-manual', state.owned.has(method.id) && !imported)
    btn.innerHTML = `<span>${method.name}</span>${imported ? '<small>자동 연결</small>' : state.owned.has(method.id) ? '<small>직접 추가</small>' : ''}`
  }
  renderChip()

  btn.addEventListener('click', () => {
    if (state.owned.has(method.id)) {
      state.owned.delete(method.id)
      state.autoImported.delete(method.id)
      btn.setAttribute('aria-pressed', 'false')
    } else {
      state.owned.add(method.id)
      btn.setAttribute('aria-pressed', 'true')
    }
    renderChip()
    const user = DEMO_USERS.find(item => item.id === state.currentUserId)
    if (user) setMyDataStatus('connected', user)
    updateSubmitLabel()
    syncDemoUserSummary()
  })
  return btn
}

function updateSubmitLabel() {
  const btn = document.querySelector('#onboardingSubmit')
  btn.disabled = state.isConnecting
  btn.textContent = state.isConnecting
    ? '마이데이터에서 불러오는 중...'
    : state.owned.size > 0
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
    btn.className = 'map-category-button'
    if (state.preferences.includes(f.key)) btn.classList.add('is-preferred')
    btn.dataset.category = f.key
    btn.style.setProperty('--category-color', categoryColor(f.key))
    btn.setAttribute('aria-pressed', String(state.category === f.key))
    btn.innerHTML = `<span aria-hidden="true">${f.icon}</span>${f.label}`
    btn.addEventListener('click', () => {
      state.category = f.key
      mapStoreCard.hidden = true
      selectedMarker = null
      document.querySelectorAll('#categoryFilters .map-category-button').forEach(b =>
        b.setAttribute('aria-pressed', String(b.dataset.category === f.key)))
      render()
      if (map && f.key === 'culture') fitVisibleStores()
      else if (map && f.key !== 'all') fitVisibleStores()
      else if (map) fitServiceArea()
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
  bounds.extend(new kakao.maps.LatLng(37.5795, 127.0465))
  bounds.extend(new kakao.maps.LatLng(37.5980, 127.0640))
  map.setBounds(bounds, 50, 50, 50, 50)
}

function fitVisibleStores() {
  const stores = visibleStores()
  if (!stores.length) return
  const bounds = new kakao.maps.LatLngBounds()
  stores.forEach(store => bounds.extend(new kakao.maps.LatLng(store.lat, store.lng)))
  map.setBounds(bounds, 60, 60, 60, 60)
}

function initMap() {
  const center = new kakao.maps.LatLng(37.5930, 127.0555)
  map = new kakao.maps.Map(document.querySelector('#map'), { center, level: 4 })
  map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT)
  document.querySelector('#recenterButton').addEventListener('click', fitServiceArea)
  fitServiceArea()
}

function areaLabel(store) {
  const name = getDisplayName(store)
  if (store.category === 'culture' && !store.address.includes('동대문구')) return '서울'
  if (name.includes('청량리') || store.lat < 37.585) return '청량리'
  if (name.includes('외대') || store.lng >= 127.0595) return '외대앞'
  if (name.includes('회기') || store.lat < 37.592) return '회기역'
  return '경희대'
}

function markerBenefitLabel(plan, references) {
  const records = plan?.benefits?.length ? plan.benefits : references
  const record = records.find(item => item.benefit.storeId || item.benefit.nameIncludes || item.benefit.brand) || records[0]
  return record?.label || ''
}

function planBenefitLabel(plan) {
  const labels = [...new Set((plan?.benefits || []).map(record => record.label).filter(Boolean))]
  if (labels.length <= 2) return labels.join(' + ')
  return `${labels.slice(0, 2).join(' + ')} 외 ${labels.length - 2}개`
}

function markerColor(store) {
  if (state.category === 'all') return categoryColor(store.category)
  if (['convenience', 'culture', 'lifestyle'].includes(state.category)) {
    return storeStyle(store.brand || detectBrand(getDisplayName(store)), store.category).color
  }
  return categoryColor(store.category)
}

function isConfirmedReference(record) {
  return record?.benefit?.verified === true
}

// 전체 보기에서는 참고 혜택을 업종색 점으로 최소화한다.
// 편의점·영화·생활편의 필터에서는 브랜드색 상세 마커로 펼쳐 보여준다.
function categoryMarker(store, plan, references = []) {
  const name = getDisplayName(store)
  const saving = plan?.saving || 0
  const preferred = state.preferences.includes(store.category)
  const referenceOnly = saving === 0 && references.length > 0
  const compactReference = referenceOnly && state.category === 'all'
  const color = markerColor(store)
  if (compactReference) {
    return `<span class="benefit-dot" style="--category-color:${color}" title="${name} · ${markerBenefitLabel(plan, references)}"></span>`
  }
  return `<span class="discount-marker${referenceOnly ? ' reference-expanded' : ' has-saving'}" style="--category-color:${color}">
    <span class="category-spot" aria-hidden="true"></span>
    <span class="marker-place"><small>${areaLabel(store)}</small><b>${name}</b></span>
    <strong>${markerBenefitLabel(plan, references)}</strong>
    ${preferred ? '<i class="personal-marker-tag">맞춤</i>' : ''}
  </span>`
}

function storeDetails(store, plan, recs, references = []) {
  const name = getDisplayName(store)
  const catLabel = CATEGORY_FILTERS.find(c => c.key === store.category)?.label || ''
  const distance = formatDistance(distanceKm(state.location, store))

  let body = ''
  if (plan && plan.saving > 0) {
    const partRows = plan.benefits.map(r =>
      `<div class="map-popup-offer">
        <span>${r.method.issuer} ${r.method.name}</span>
        <strong>${r.label}</strong>
      </div>
      <p class="map-popup-condition">${r.benefit.cond || ''} · 출처: ${r.benefit.evidence || '미기재'}</p>`).join('')
    const header = `<div class="map-popup-best">
        ${plan.combo ? '검증된 최적 조합' : plan.cashRestricted ? '검증된 현금 혜택' : '검증된 최적 혜택'} <b>${planBenefitLabel(plan)}</b>
      </div>`
    body = header + partRows
  }

  if (references.length) {
    const confirmed = references.filter(isConfirmedReference)
    const unconfirmed = references.filter(record => !isConfirmedReference(record))
    if (confirmed.length) {
      body += `<div class="reference-benefits confirmed-benefits">
        <b>공식 혜택 · 결제 조건에 따라 할인액 변동</b>
        ${confirmed.slice(0, 3).map(r => `<p>${r.method.issuer} ${r.method.name}: ${r.label}<br><small>${r.benefit.cond || ''}</small></p>`).join('')}
      </div>`
    }
    if (unconfirmed.length) {
      body += `<div class="reference-benefits${plan?.saving > 0 ? '' : ' reference-only-details'}">
        <b>${plan?.saving > 0 || confirmed.length ? '추가 참고 혜택 · 금액 계산 제외' : '참고 혜택 · 적용 조건 확인 필요'}</b>
        ${unconfirmed.slice(0, 3).map(r => `<p>${r.method.issuer} ${r.method.name}: ${r.label}<br><small>${r.referenceReason} · ${r.benefit.cond || ''}</small></p>`).join('')}
      </div>`
    }
  }

  const preferred = state.preferences.includes(store.category)
  return `<div class="map-popup">
    <p class="map-popup-brand">${areaLabel(store)} · ${catLabel}${preferred ? ' · 내 관심 업종' : ''}</p>
    <h3>${name}</h3>
    <span class="map-popup-address">현재 위치에서 ${distance} · ${store.address}</span>
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
  return state.stores.filter(store => {
    const recommendations = getRecommendations(store, state.active, state.spend, planOpts())
    const references = getReferenceRecommendations(store, state.active, state.spend, planOpts())
    const hasBenefit = recommendations.some(item => item.saving > 0) || references.length > 0
    if (!hasBenefit) return false
    if (state.category === 'campus') {
      return store.category === 'campus' || recommendations.concat(references)
        .some(item => item.method.id === 'khu_alliance' || item.method.id === 'student_card' || item.method.id === 'student_tok')
    }
    return state.category === 'all' || store.category === state.category
  })
}

function updateMap() {
  if (!map) return
  storeOverlays.forEach(o => o.setMap(null))
  storeOverlays = []
  locationOverlay?.setMap(null)
  selectedMarker = null
  mapStoreCard.hidden = true

  const stores = visibleStores()
  const mapSearch = document.querySelector('.map-search')
  mapSearch.innerHTML = `<strong>${stores.length}곳</strong> · 경희대 · 회기역 · 외대앞 내 혜택`

  stores.forEach(store => {
    const recs = getRecommendations(store, state.active, state.spend, planOpts())
    const references = getReferenceRecommendations(store, state.active, state.spend, planOpts())
    const plan = computeBestPlan(store, state.active, state.spend, planOpts())
    const details = storeDetails(store, plan, recs, references)
    const preferred = state.preferences.includes(store.category)
    const preferenceRank = state.preferences.indexOf(store.category)
    const referenceOnly = plan.saving === 0
    const expandedReference = referenceOnly && state.category !== 'all'
    const baseZIndex = referenceOnly ? 2 : preferenceRank < 0 ? 10 : 30 - preferenceRank
    const el = document.createElement('button')
    el.type = 'button'
    el.className = `store-icon${referenceOnly && !expandedReference ? ' is-reference-only' : ''}`
    const name = getDisplayName(store)
    const catLabel = CATEGORY_FILTERS.find(item => item.key === store.category)?.label || ''
    const savingLabel = markerBenefitLabel(plan, references)
    const confirmedReference = referenceOnly && references.some(isConfirmedReference)
    el.setAttribute('aria-label', `${areaLabel(store)} ${name}, ${catLabel}, ${savingLabel}${referenceOnly && !confirmedReference ? ', 적용 조건 확인 필요' : ''}`)
    el.innerHTML = referenceOnly && !expandedReference
      ? `<span class="store-marker">${categoryMarker(store, plan, references)}</span>`
      : `<span class="store-marker">${categoryMarker(store, plan, references)}</span><span class="marker-hover">${details}</span>`
    const overlay = new kakao.maps.CustomOverlay({
      map,
      position: new kakao.maps.LatLng(store.lat, store.lng),
      content: el,
      yAnchor: 0.5,
      zIndex: baseZIndex,
    })
    el.addEventListener('mouseenter', () => overlay.setZIndex(1000))
    el.addEventListener('mouseleave', () => overlay.setZIndex(el.classList.contains('is-selected') ? 900 : baseZIndex))
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

  const preferenceScore = item => {
    const index = state.preferences.indexOf(item.store.category)
    const categoryWeight = index < 0 ? 0 : (state.preferences.length - index) * 100000
    const verifiedSaving = (item.plan?.saving || 0) * 10
    const referenceWeight = item.references.length ? 100 : 0
    return categoryWeight + verifiedSaving + referenceWeight
  }

  stores.sort(state.sort === 'discount'
    ? (a, b) => (b.plan?.saving || 0) - (a.plan?.saving || 0) || a.distance - b.distance
    : state.sort === 'personalized'
      ? (a, b) => preferenceScore(b) - preferenceScore(a) || a.distance - b.distance
      : (a, b) => a.distance - b.distance || (b.plan?.saving || 0) - (a.plan?.saving || 0))

  list.replaceChildren()
  stores.forEach(({ store, recs, references, plan, distance }) => {
    const card = document.createElement('article')
    card.className = `benefit-card ${plan.saving > 0 ? 'has-saving' : 'is-reference-only'}`
    const name = getDisplayName(store)
    const catLabel = CATEGORY_FILTERS.find(c => c.key === store.category)?.label || ''
    const preferred = state.preferences.includes(store.category)

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
    // 공식 혜택과 미확인 참고 혜택을 구분한다.
    const referenceRows = references.slice(0, 3).map(r => {
      const confirmed = isConfirmedReference(r)
      return `<li class="reference-rec">
        <span>${r.method.issuer} ${r.method.name}<small>${confirmed ? r.benefit.cond || '' : `${r.referenceReason} · ${r.benefit.cond || ''}`}</small></span>
        <em>${r.label} <i class="verify-tag mini${confirmed ? ' ok' : ''}">${confirmed ? '공식' : '계산 제외'}</i></em>
      </li>`
    }).join('')
    const hasConfirmedReference = references.some(isConfirmedReference)

    card.style.setProperty('--category-color', markerColor(store))
    card.innerHTML = `
      <div class="card-content">
        <div class="card-topline">
          <span class="store-name"><i class="category-dot" aria-hidden="true"></i>${name}${preferred ? '<small class="personal-fit">내 관심 업종</small>' : ''}</span>
          <span class="distance">${formatDistance(distance)}</span>
        </div>
        <p class="address"><strong>${areaLabel(store)}</strong> · 현재 위치에서 ${formatDistance(distance)}<br>${catLabel} · ${store.address}</p>
        ${plan.saving > 0 ? `
          <div class="offer-row">
            <span class="pay-badge best-pay">${plan.combo ? '검증된 최적 조합' : plan.cashRestricted ? '검증된 현금 혜택' : '검증된 최적 혜택'}</span>
            <p><strong class="discount">${planBenefitLabel(plan)}</strong></p>
          </div>
          <ul class="plan-parts">${partRows}</ul>
          ${others ? `<p class="alt-label">다른 검증 옵션</p><ul class="other-recs">${others}</ul>` : ''}
        ` : ''}
        ${referenceRows ? `<p class="alt-label reference-label">${hasConfirmedReference ? '공식 혜택' : plan.saving > 0 ? '추가 참고 혜택' : '참고 혜택 · 적용 조건 확인 필요'} <small>${hasConfirmedReference ? '결제 조건에 따라 혜택 변동' : '추천 금액 계산 제외'}</small></p><ul class="other-recs reference-recs">${referenceRows}</ul>` : ''}
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
      loadStores(() => {
        render()
        if (state.category !== 'all') fitVisibleStores()
      }) // 자동수집 완료 후 실제 매장으로 교체하고 선택 업종 범위에 맞춤
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
