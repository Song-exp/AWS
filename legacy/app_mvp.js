const payMethods = {
  kakao: { name: '카카오페이', short: 'Kakao Pay', className: 'kakao' },
  toss: { name: '토스페이', short: 'Toss Pay', className: 'toss' },
  naver: { name: '네이버페이', short: 'N Pay', className: 'naver' }
};

const standardOffers = {
  kakao: [5, '1만원 이상 결제 · 최대 2천원'],
  toss: [7, '토스페이머니 결제 · 최대 2천원'],
  naver: [10, 'N포인트 결제 시 · 최대 3천원']
};

const stores = [
  { brand: 'CU', branch: '경희대점', mark: 'CU', color: '#7b2cbf', address: '경희대로4길 15', lat: 37.592493, lng: 127.053511, offers: standardOffers },
  { brand: 'GS25', branch: '경희의대점', mark: 'GS', color: '#0879c9', address: '회기로23가길 21', lat: 37.592324, lng: 127.054227, offers: standardOffers },
  { brand: '세븐일레븐', branch: '경희대기숙사점', mark: '7', color: '#e31e24', address: '이문로9길 46', lat: 37.594255, lng: 127.056536, offers: standardOffers },
  { brand: '이마트24 생협', branch: '음악대점', mark: '24', color: '#f5c400', address: '음악대학·크라운관', lat: 37.5956709, lng: 127.0554938, offers: standardOffers },
  { brand: '이마트24 생협', branch: '생과대위성점', mark: '24', color: '#f5c400', address: '생활과학대학', lat: 37.5938555, lng: 127.0548619, offers: standardOffers },
  { brand: '이마트24 생협', branch: '생과대점', mark: '24', color: '#f5c400', address: '생활과학대학 B1', lat: 37.5960401, lng: 127.0513379, offers: standardOffers },
  { brand: '이마트24 생협', branch: '의과대위성점', mark: '24', color: '#f5c400', address: '의과대학', lat: 37.594731, lng: 127.054399, offers: standardOffers },
  { brand: '이마트24 생협', branch: '청운관위성점', mark: '24', color: '#f5c400', address: '청운관', lat: 37.594885, lng: 127.0518096, offers: standardOffers },
  { brand: '이마트24 생협', branch: '경영대점', mark: '24', color: '#f5c400', address: '경영대학', lat: 37.5966857, lng: 127.0554092, offers: standardOffers },
  { brand: '이마트24 생협', branch: '도서관점', mark: '24', color: '#f5c400', address: '중앙도서관', lat: 37.5967479, lng: 127.0531776, offers: standardOffers },
  { brand: '이마트24 생협', branch: '의과대점', mark: '24', color: '#f5c400', address: '의과대학', lat: 37.5940081, lng: 127.0545734, offers: standardOffers },
  { brand: '이마트24 생협', branch: '간호이과대위성점', mark: '24', color: '#f5c400', address: '간호과학대학·이과대학', lat: 37.5955125, lng: 127.0536969, offers: standardOffers },
  { brand: '이마트24 생협', branch: '간호이과대점', mark: '24', color: '#f5c400', address: '간호과학대학·이과대학', lat: 37.5954571, lng: 127.0536066, offers: standardOffers },
  { brand: '이마트24 생협', branch: '정경대점', mark: '24', color: '#f5c400', address: '정경대학', lat: 37.5973204, lng: 127.0555079, offers: standardOffers },
  { brand: '이마트24 생협', branch: '푸른솔문화관점', mark: '24', color: '#f5c400', address: '푸른솔문화관', lat: 37.5950277, lng: 127.0544437, offers: standardOffers },
  { brand: '이마트24 생협', branch: '문과대점', mark: '24', color: '#f5c400', address: '문과대학', lat: 37.5971625, lng: 127.0541721, offers: standardOffers },
  { brand: '이마트24 생협', branch: '청운관점', mark: '24', color: '#f5c400', address: '청운관', lat: 37.5937444, lng: 127.0532231, offers: standardOffers },
  { brand: 'GS25', branch: '경희정문점', mark: 'GS', color: '#0879c9', address: '경희대로 정문 앞', lat: 37.5926702, lng: 127.0524544, offers: standardOffers },
  { brand: 'GS25', branch: '이문회기점', mark: 'GS', color: '#0879c9', address: '회기로25길 54', lat: 37.592105, lng: 127.056759, offers: standardOffers },
  { brand: 'CU', branch: '카이스트점', mark: 'CU', color: '#7b2cbf', address: '회기로 119', lat: 37.591598, lng: 127.049904, offers: standardOffers },
  { brand: 'GS25', branch: '카이스트원룸점', mark: 'GS', color: '#0879c9', address: '회기로 118', lat: 37.591332, lng: 127.049674, offers: standardOffers },
  { brand: 'GS25', branch: '경희원룸점', mark: 'GS', color: '#0879c9', address: '이문로3길 66', lat: 37.590936, lng: 127.051562, offers: standardOffers },
  { brand: '세븐일레븐', branch: '경희대대현점', mark: '7', color: '#e31e24', address: '회기로 163', lat: 37.590871, lng: 127.054273, offers: standardOffers },
  { brand: 'CU', branch: '회기중앙점', mark: 'CU', color: '#7b2cbf', address: '회기로29길 9', lat: 37.590577, lng: 127.05791, offers: standardOffers },
  { brand: 'GS25', branch: '청량현대점', mark: 'GS', color: '#0879c9', address: '이문로1길 21', lat: 37.590168, lng: 127.051564, offers: standardOffers },
  { brand: '세븐일레븐', branch: '회기해피파크점', mark: '7', color: '#e31e24', address: '이문로 19', lat: 37.589825, lng: 127.05517, offers: standardOffers },
  { brand: 'CU', branch: '회기나무점', mark: 'CU', color: '#7b2cbf', address: '이문로 18', lat: 37.589273, lng: 127.055308, offers: standardOffers },
  { brand: '이마트24', branch: 'JLL회기로점', mark: '24', color: '#f5c400', address: '회기로29길 34', lat: 37.591682, lng: 127.0582606, offers: standardOffers },
  { brand: 'GS25', branch: '외대서문점', mark: 'GS', color: '#0879c9', address: '이문로 100', lat: 37.5957355, lng: 127.0599767, offers: standardOffers },
  { brand: 'CU', branch: '외대앞점', mark: 'CU', color: '#7b2cbf', address: '휘경로 24-1', lat: 37.5952326, lng: 127.0625862, offers: standardOffers },
  { brand: 'GS25', branch: '외대앞점', mark: 'GS', color: '#0879c9', address: '휘경로 10', lat: 37.59596, lng: 127.0610948, offers: standardOffers },
  { brand: '세븐일레븐', branch: '외대정문점', mark: '7', color: '#e31e24', address: '이문로 112', lat: 37.5965879, lng: 127.0605365, offers: standardOffers },
  { brand: '이마트24', branch: '외대앞역점', mark: '24', color: '#f5c400', address: '휘경로 18-1', lat: 37.5955558, lng: 127.0618884, offers: standardOffers },
  { brand: 'CU', branch: '외대후문점', mark: 'CU', color: '#7b2cbf', address: '휘경로2길 25', lat: 37.5948551, lng: 127.0603927, offers: standardOffers },
  { brand: 'GS25', branch: '외대역동로점', mark: 'GS', color: '#0879c9', address: '휘경로14길 16', lat: 37.5945394, lng: 127.0630638, offers: standardOffers }
];

const state = { pay: new Set(Object.keys(payMethods)), sort: 'distance', location: { lat: 37.5943, lng: 127.0537 } };
const filterRoot = document.querySelector('#payFilters');
const list = document.querySelector('#benefitList');
const template = document.querySelector('#benefitTemplate');
const emptyState = document.querySelector('#emptyState');
const mapView = document.querySelector('#mapView');
let map;
let storeOverlays = [];
let locationOverlay;
let selectedMarker;
const mapStoreCard = document.querySelector('#mapStoreCard');

function distanceKm(a, b) {
  const rad = value => value * Math.PI / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const value = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

function formatDistance(km) {
  return km < 1 ? `${Math.max(10, Math.round(km * 1000 / 10) * 10)}m` : `${km.toFixed(1)}km`;
}

function buildFilters() {
  Object.entries(payMethods).forEach(([id, pay]) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `pay-filter ${pay.className}`;
    button.dataset.pay = id;
    button.setAttribute('aria-pressed', 'true');
    button.textContent = pay.name;
    filterRoot.append(button);
  });
}

function fitServiceArea() {
  const bounds = new kakao.maps.LatLngBounds();
  bounds.extend(new kakao.maps.LatLng(37.5891, 127.0493));
  bounds.extend(new kakao.maps.LatLng(37.5982, 127.0635));
  map.setBounds(bounds, 50, 50, 50, 50);
}

function initMap() {
  const center = new kakao.maps.LatLng(37.5938, 127.0564);
  map = new kakao.maps.Map(document.querySelector('#map'), { center, level: 4 });
  map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
  document.querySelector('#recenterButton').addEventListener('click', fitServiceArea);
  fitServiceArea();
}

function brandLogo(store) {
  if (store.brand === 'CU') return '<span class="brand-logo logo-cu"><b>C</b><i>U</i></span>';
  if (store.brand === 'GS25') return '<img class="brand-logo logo-image logo-gs" src="logo-gs25.png" alt="">';
  if (store.brand === '세븐일레븐') return '<img class="brand-logo logo-image logo-seven" src="logo-seven.png" alt="">';
  return '<img class="brand-logo logo-image logo-emart" src="logo-emart24.png" alt="">';
}

function storeDetails(store, offers) {
  const offerRows = offers.map(([pay, [discount]]) =>
    `<div class="map-popup-offer"><span>${payMethods[pay].name}</span><strong>${discount}%</strong></div>`
  ).join('');
  return `<div class="map-popup"><p class="map-popup-brand">${store.brand}</p><h3>${store.branch}</h3><span class="map-popup-address">${store.address}</span>${offerRows}</div>`;
}

function selectStore(element, details) {
  selectedMarker?.classList.remove('is-selected');
  selectedMarker = element;
  element.classList.add('is-selected');
  mapStoreCard.innerHTML = `${details}<button type="button" aria-label="상세 닫기">×</button>`;
  mapStoreCard.hidden = false;
  mapStoreCard.querySelector('button').addEventListener('click', () => {
    mapStoreCard.hidden = true;
    element.classList.remove('is-selected');
    selectedMarker = null;
  });
}

function updateMap() {
  if (!map) return;
  storeOverlays.forEach(overlay => overlay.setMap(null));
  storeOverlays = [];
  locationOverlay?.setMap(null);
  selectedMarker = null;
  mapStoreCard.hidden = true;

  stores.forEach(store => {
    const offers = Object.entries(store.offers).filter(([pay]) => state.pay.has(pay));
    if (!offers.length) return;
    const details = storeDetails(store, offers);
    const element = document.createElement('button');
    element.type = 'button';
    element.className = 'store-icon';
    element.setAttribute('aria-label', `${store.brand} ${store.branch}`);
    element.innerHTML = `<span class="store-marker">${brandLogo(store)}</span><span class="marker-label">${store.branch.replace('위성점', ' 위성')}</span><span class="marker-hover">${details}</span>`;
    const overlay = new kakao.maps.CustomOverlay({
      map,
      position: new kakao.maps.LatLng(store.lat, store.lng),
      content: element,
      yAnchor: 0.5,
      zIndex: 3
    });
    element.addEventListener('mouseenter', () => overlay.setZIndex(1000));
    element.addEventListener('mouseleave', () => overlay.setZIndex(element.classList.contains('is-selected') ? 900 : 3));
    element.addEventListener('focus', () => overlay.setZIndex(1000));
    element.addEventListener('blur', () => overlay.setZIndex(element.classList.contains('is-selected') ? 900 : 3));
    element.addEventListener('click', event => {
      event.stopPropagation();
      overlay.setZIndex(900);
      selectStore(element, details);
    });
    storeOverlays.push(overlay);
  });

  const locationElement = document.createElement('span');
  locationElement.className = 'current-location';
  locationElement.title = '기준 위치';
  locationOverlay = new kakao.maps.CustomOverlay({
    map,
    position: new kakao.maps.LatLng(state.location.lat, state.location.lng),
    content: locationElement,
    zIndex: 2
  });
}

function render() {
  const items = stores.flatMap(store => Object.entries(store.offers)
    .filter(([pay]) => state.pay.has(pay))
    .map(([pay, [discount, condition]]) => ({ ...store, pay, discount, condition, distance: distanceKm(state.location, store) })));

  items.sort(state.sort === 'discount'
    ? (a, b) => b.discount - a.discount || a.distance - b.distance
    : (a, b) => a.distance - b.distance || b.discount - a.discount);

  list.replaceChildren();
  items.forEach(item => {
    const card = template.content.cloneNode(true);
    const logo = card.querySelector('.store-logo');
    logo.innerHTML = brandLogo(item);
    logo.classList.add('has-brand-logo');
    card.querySelector('.store-name').textContent = `${item.brand} ${item.branch}`;
    card.querySelector('.distance').textContent = formatDistance(item.distance);
    card.querySelector('.address').textContent = item.address;
    const badge = card.querySelector('.pay-badge');
    badge.textContent = payMethods[item.pay].short;
    badge.classList.add(payMethods[item.pay].className);
    card.querySelector('.discount').textContent = `${item.discount}%`;
    card.querySelector('.condition').textContent = item.condition;
    list.append(card);
  });

  document.querySelector('#resultCount').textContent = items.length;
  emptyState.hidden = items.length > 0;
  updateMap();
}

function setView(view) {
  const showMap = view === 'map';
  mapView.hidden = !showMap;
  list.hidden = showMap;
  document.querySelector('.sort-label').hidden = showMap;
  document.querySelectorAll('.view-button').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.view === view));
  });
  if (showMap) setTimeout(() => map.relayout(), 0);
}

document.querySelector('.view-toggle').addEventListener('click', event => {
  const button = event.target.closest('.view-button');
  if (button) setView(button.dataset.view);
});

filterRoot.addEventListener('click', event => {
  const button = event.target.closest('.pay-filter');
  if (!button) return;
  const pay = button.dataset.pay;
  state.pay.has(pay) ? state.pay.delete(pay) : state.pay.add(pay);
  button.setAttribute('aria-pressed', String(state.pay.has(pay)));
  render();
});

document.querySelector('#sortSelect').addEventListener('change', event => {
  state.sort = event.target.value;
  render();
});

function resetFilters() {
  Object.keys(payMethods).forEach(pay => state.pay.add(pay));
  document.querySelectorAll('.pay-filter').forEach(button => button.setAttribute('aria-pressed', 'true'));
  render();
}

document.querySelector('#resetButton').addEventListener('click', resetFilters);
emptyState.querySelector('button').addEventListener('click', resetFilters);

document.querySelector('#locationButton').addEventListener('click', () => {
  const status = document.querySelector('#locationStatus');
  if (!navigator.geolocation) {
    status.textContent = '이 브라우저에서는 위치 기능을 사용할 수 없어요.';
    return;
  }
  status.textContent = '현재 위치를 확인하고 있어요…';
  navigator.geolocation.getCurrentPosition(position => {
    state.location = { lat: position.coords.latitude, lng: position.coords.longitude };
    status.textContent = '현재 위치를 기준으로 가까운 혜택을 보여드려요.';
    map.setLevel(3);
    map.panTo(new kakao.maps.LatLng(state.location.lat, state.location.lng));
    render();
  }, () => {
    status.textContent = '위치 권한이 없어 경희대학교 주변의 데모 혜택을 보여드려요.';
  }, { enableHighAccuracy: true, timeout: 8000 });
});

buildFilters();

function startMap() {
  if (window.kakao?.maps) {
    kakao.maps.load(() => {
      initMap();
      render();
    });
    return;
  }

  document.querySelector('#map').innerHTML = '<p class="map-error">카카오맵을 불러오지 못했어요.<br>config.js의 JavaScript 키와 허용 도메인을 확인해 주세요.</p>';
  setView('list');
  render();
}

if (window.kakao?.maps) startMap();
else window.addEventListener('kakao-sdk-ready', startMap, { once: true });