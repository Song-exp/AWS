// ═══════════════════════════════════════════════════════════
// 페이픽 + 거지앱 통합 앱 로직
// ═══════════════════════════════════════════════════════════

const CATEGORY_FILTERS = [
  { key: 'all', label: '전체', emoji: '📍' },
  { key: 'restaurant', label: '음식점', emoji: '🍽️' },
  { key: 'cafe', label: '카페', emoji: '☕' },
  { key: 'convenience', label: '편의점', emoji: '🏪' },
]

// 자동수집 기준: 회기 스타벅스 사거리 중심 500m
const CENTER = { lat: 37.5894, lng: 127.0562 }
const SEARCH_RADIUS = 500
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
  convenience: { color: '#0879c9', mark: '🏪' },
  cafe: { color: '#00704a', mark: '☕' },
  restaurant: { color: '#e8552d', mark: '🍽️' },
}
function storeStyle(brand, cat) {
  return BRAND_STYLE[brand] || CAT_STYLE[cat] || { color: '#5b5ce2', mark: '•' }
}

const state = {
  owned: new Set(),          // 온보딩에서 고른 보유 결제수단 id
  active: new Set(),         // 메인 화면에서 켜져있는(필터) 수단 id
  category: 'all',           // 업종 필터
  sort: 'distance',
  location: { lat: CENTER.lat, lng: CENTER.lng },
  spend: 10000,
  stores: STORES,            // 기본은 정적 데이터, 자동수집 성공 시 교체
  profile: { naverPlus: false, kakaoPlus: false, telecomGrade: 'vip' }, // 멤버십/등급
}

// 추천 계산에 넘길 옵션(프로필)
function planOpts() {
  return { profile: state.profile }
}

function getDisplayName(store) {
  return store.name || (store.brand ? `${store.brand} ${store.branch}` : store.branch)
}

// ─── 혜택 데이터 외부 소스 로드 (코드 배포 없이 갱신) ───
// 지금은 benefits.json, 추후 서버 API URL로 교체하면 그대로 실시간 갱신됨.
const BENEFITS_SOURCE = 'benefits.json'
async function loadBenefits() {
  try {
    const res = await fetch(BENEFITS_SOURCE, { cache: 'no-store' })
    if (!res.ok) return
    const json = await res.json()
    if (json && Array.isArray(json.benefits)) {
      setBenefits(json.benefits)
      state.benefitsUpdatedAt = json.updatedAt || null
      updateDataNote()
    }
  } catch (e) {
    // 네트워크 실패 시 data.js의 시드 BENEFITS로 폴백
    console.warn('benefits.json 로드 실패 — 내장 시드 데이터 사용', e)
  }
}

function updateDataNote() {
  const el = document.querySelector('.notice')
  if (el && state.benefitsUpdatedAt) {
    el.textContent = `혜택 데이터 기준일 ${state.benefitsUpdatedAt} · 유효기간 지난 혜택은 자동 제외됩니다. (MVP 예시 데이터 포함)`
  }
}

// ─── 카카오 장소검색으로 매장 자동수집 ───
function loadStores(done) {
  const k = window.kakao
  if (!(k && k.maps && k.maps.services)) {
    state.stores = STORES
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
    collected.forEach(s => { if (!seen.has(s.id)) { seen.add(s.id); uniq.push(s) } })
    state.stores = uniq.length ? uniq : STORES
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

let map
let storeOverlays = []
let locationOverlay
let selectedMarker

// ═══════════════════════════════════════════
// 온보딩
// ═══════════════════════════════════════════
function buildOnboarding() {
  onboardingGroups.innerHTML = ''
  PAYMENT_GROUPS.forEach(group => {
    const section = document.createElement('section')
    section.className = 'ob-group'

    const h = document.createElement('h3')
    h.innerHTML = `<span>${group.emoji}</span> ${group.label}`
    section.append(h)

    // 카드는 발급사별로 하위 그룹
    if (group.category === 'card') {
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
  section.innerHTML = `<h3><span>⭐</span> 멤버십 / 등급 <small>(선택 — 혜택 정확도 ↑)</small></h3>`

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
  btn.setAttribute('aria-pressed', 'false')
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
    ? `${state.owned.size}개 선택 완료 → 시작하기`
    : '선택하고 시작하기'
}

document.querySelector('#onboardingSubmit').addEventListener('click', () => {
  if (state.owned.size === 0) {
    alert('결제수단을 최소 1개 이상 선택해주세요!')
    return
  }
  onboarding.hidden = true
  appMain.hidden = false
  // 보유 수단을 전부 활성화 상태로 시작
  state.active = new Set(state.owned)
  myMethodsChip.textContent = `내 수단 ${state.owned.size}개`
  buildMethodFilters()
  startMap()
})

document.querySelector('#editMethodsButton').addEventListener('click', () => {
  appMain.hidden = true
  onboarding.hidden = false
})

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
    btn.textContent = `${f.emoji} ${f.label}`
    btn.addEventListener('click', () => {
      state.category = f.key
      document.querySelectorAll('#categoryFilters .pay-filter').forEach(b =>
        b.setAttribute('aria-pressed', String(b.dataset.category === f.key)))
      render()
    })
    categoryFilterRoot.append(btn)
  })
}

myMethodsChip.addEventListener('click', () => {
  appMain.hidden = true
  onboarding.hidden = false
})

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
      btn.innerHTML = `<span class="mf-emoji">${group.emoji}</span> ${label}`
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
  bounds.extend(new kakao.maps.LatLng(37.5885, 127.0490))
  bounds.extend(new kakao.maps.LatLng(37.5975, 127.0635))
  map.setBounds(bounds, 50, 50, 50, 50)
}

function initMap() {
  const center = new kakao.maps.LatLng(37.5930, 127.0555)
  map = new kakao.maps.Map(document.querySelector('#map'), { center, level: 4 })
  map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT)
  document.querySelector('#recenterButton').addEventListener('click', fitServiceArea)
  fitServiceArea()
}

// 업종별 마커 표시
function categoryMarker(store) {
  const emoji = store.category === 'cafe' ? '☕'
    : store.category === 'restaurant' ? '🍽️' : '🏪'
  return `<span class="cat-marker" style="--marker-color:${store.color}">${store.mark || emoji}</span>`
}

function storeDetails(store, plan, recs) {
  const name = getDisplayName(store)
  const catLabel = CATEGORY_FILTERS.find(c => c.key === store.category)?.label || ''

  let body
  if (!plan || plan.saving <= 0) {
    body = '<div class="map-popup-offer"><span>사용 가능한 혜택 없음</span></div>'
  } else {
    const partRows = plan.benefits.map(r =>
      `<div class="map-popup-offer">
        <span>${r.method.emoji} ${r.method.issuer} ${r.method.name}</span>
        <strong>${r.label}</strong>
      </div>`).join('')
    const header = `<div class="map-popup-best">
        ${plan.combo ? '🏆 최적 조합' : '🏆 최적'} <b>-${plan.saving.toLocaleString()}원</b>
        <span class="popup-spend">1만원 결제 기준</span>
      </div>`
    body = header + partRows
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
    const plan = computeBestPlan(store, state.active, state.spend, planOpts())
    const details = storeDetails(store, plan, recs)
    const el = document.createElement('button')
    el.type = 'button'
    el.className = 'store-icon'
    const name = getDisplayName(store)
    el.setAttribute('aria-label', name)
    const best = plan
    el.innerHTML = `
      <span class="store-marker">${categoryMarker(store)}</span>
      ${best ? `<span class="marker-badge">-${best.saving.toLocaleString()}원</span>` : ''}
      <span class="marker-label">${store.branch}</span>
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
    const plan = computeBestPlan(store, state.active, state.spend, planOpts())
    return { store, recs, plan, distance: distanceKm(state.location, store) }
  })

  stores.sort(state.sort === 'discount'
    ? (a, b) => (b.plan?.saving || 0) - (a.plan?.saving || 0) || a.distance - b.distance
    : (a, b) => a.distance - b.distance || (b.plan?.saving || 0) - (a.plan?.saving || 0))

  list.replaceChildren()
  stores.forEach(({ store, recs, plan, distance }) => {
    const card = document.createElement('article')
    card.className = 'benefit-card'
    const name = getDisplayName(store)
    const catLabel = CATEGORY_FILTERS.find(c => c.key === store.category)?.label || ''
    const catEmoji = store.category === 'cafe' ? '☕' : store.category === 'restaurant' ? '🍽️' : '🏪'

    // 조합 구성요소
    const planIds = new Set(plan.benefits.map(r => r.benefit.id))
    const partRows = plan.benefits.map(r =>
      `<li>
        <span>${r.method.emoji} ${r.method.issuer} ${r.method.name}</span>
        <em>${r.label}${r.benefit.verified === false ? ' <i class="verify-tag mini">예시</i>' : ''}</em>
      </li>`).join('')
    // 조합에 안 쓰인 다른 옵션(참고)
    const others = recs.filter(r => !planIds.has(r.benefit.id)).slice(0, 2).map(r =>
      `<li class="alt"><span>${r.method.issuer} ${r.method.name}</span><em>${r.label}</em></li>`).join('')

    card.innerHTML = `
      <div class="store-logo" style="background:${store.color}">${store.mark || catEmoji}</div>
      <div class="card-content">
        <div class="card-topline">
          <span class="store-name">${name}</span>
          <span class="distance">${formatDistance(distance)}</span>
        </div>
        <p class="address">${catEmoji} ${catLabel} · ${store.address}</p>
        ${plan.saving > 0 ? `
          <div class="offer-row">
            <span class="pay-badge best-pay">${plan.combo ? '🏆 최적 조합' : '🏆 최적'}</span>
            <p><strong class="discount">-${plan.saving.toLocaleString()}원</strong></p>
          </div>
          <ul class="plan-parts">${partRows}</ul>
          ${others ? `<p class="alt-label">다른 옵션</p><ul class="other-recs">${others}</ul>` : ''}
        ` : `<p class="condition">사용 가능한 혜택 없음</p>`}
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

emptyState.querySelector('button').addEventListener('click', () => {
  appMain.hidden = true
  onboarding.hidden = false
})

// ═══════════════════════════════════════════
// 지도 시작
// ═══════════════════════════════════════════
function startMap() {
  buildCategoryFilters()
  if (window.kakao?.maps) {
    kakao.maps.load(async () => {
      if (!map) initMap()
      await loadBenefits()  // 외부 소스에서 최신 혜택 로드(만료분 자동 제외)
      render()              // 정적 매장 + 최신 혜택으로 렌더
      setView('map')
      loadStores(render)    // 자동수집 완료되면 실제 매장으로 교체 렌더
    })
    return
  }
  document.querySelector('#map').innerHTML =
    '<p class="map-error">카카오맵을 불러오지 못했어요.<br>config.js의 JavaScript 키와 허용 도메인을 확인해 주세요.</p>'
  loadBenefits().then(() => { setView('list'); render() })
}

// 초기화
buildOnboarding()
updateSubmitLabel()
