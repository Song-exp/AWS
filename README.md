# 대학생 혜택 통합 서비스

지도 할인과 장학금 챗봇을 하나로 합친 앱.

- **지도(TMI)**: 내 주변 편의점·카페·음식점·마트 등의 간편결제/카드 할인 비교 → **지출 방어**
- **챗봇(장학금)**: 소득분위 기반 장학금 매칭 → 초안 생성 → 아카이빙 → **수입 확보**
- **마이페이지**: 신청 기록·재사용 자기소개서·보유 카드 조회

## 구조
```text
app/                    백엔드(FastAPI)
  core/    설정 · DB세션 · 방언독립 타입(SQLite/PostgreSQL 전환)
  models/  scholarship · application · crawl_run · store · card · user
  api/     stores · meta · me · chat · scholarships · ai · applications · admin
  crawlers/ 공공/민간 어댑터 · 월간 파이프라인
  services/ matching · rag · chat(상태머신) · indexing · llm(DeepSeek) · scheduler
  scripts/ init_all 및 개별 데이터 시드
frontend/               프론트(React + Vite + TS)
  src/pages/ OnboardingPage · MapPage · ChatPage · MyPage
  src/App.tsx 온보딩 + 하단 3탭 네비게이션
legacy/                 통합 전 정적 지도 서비스 원본(seed_stores 파싱 대상)
```

## 로컬 실행

### 1) 백엔드
```powershell
pip install --only-binary=:all: -r requirements.txt
Copy-Item .env.example .env       # DEEPSEEK_API_KEY 등 채우기

# 매장 47 + 제휴·온누리·서울Pay+·제로페이 가맹점 1,213 + 간편결제/카드 혜택 + 샘플 장학금을 멱등 적재
.\.venv\Scripts\python.exe -m app.scripts.init_all

# 샘플 대신 실제 장학금 크롤을 실행하려면
.\.venv\Scripts\python.exe -m app.scripts.init_all --scholarships crawl

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
# http://localhost:8000/docs
```
`init_all`의 장학금 모드는 `sample`(기본, 외부 통신 없음), `crawl`, `skip`이다. 크롤 대상 월은
`--month 2026-08 --month 2026-09`처럼 반복 지정할 수 있다. 각 시드는 upsert 방식이라 재실행해도 중복되지 않는다.

로컬 기본 DB는 **SQLite**(`data/app.db`)로 별도 설치가 필요 없다. 배포 시 `DATABASE_URL`을
PostgreSQL로 바꾸면 pgvector 벡터 검색까지 활성화된다.

### 2) 프론트엔드
```powershell
Set-Location frontend
npm install
Copy-Item .env.example .env       # VITE_KAKAO_MAP_KEY 채우기
npm run dev                       # http://localhost:5173
```
개발 중 `/api` 요청은 Vite 프록시로 백엔드(8000)에 전달된다. 배포 전 검증은 `npm run build`로 실행한다.

## 주요 엔드포인트
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/stores/nearby?lat=&lng=&radius_m=&pay=&card_ids=&category=&sort=` | 카테고리별 주변 매장·혜택 조회 및 최적 결제 추천 |
| GET | `/stores/local-benefits?program=&credential=&category=&offset=&limit=` | 학생제휴·온누리·서울Pay+·제로페이 가맹점 조회 |
| GET | `/stores/{id}` | 매장 상세 |
| GET | `/meta/options` | 카드·결제수단·통신사·매장 카테고리 옵션 |
| GET | `/me/summary?user_id=&card_ids=` | 신청 기록·자기소개서·보유 카드 조회 |
| POST | `/chat/message` | 챗봇 대화(LLM+백엔드 상태머신) |
| POST | `/chat/upload` | 대화 중 과거 신청서 첨부 |
| POST | `/scholarships/match` | 프로필 기반 장학금 매칭 |
| POST | `/applications/upload` | 과거 신청서 업로드(→텍스트 추출) |
| POST | `/applications` | 작성 신청서 저장(플라이휠) |
| POST | `/ai/qa` · `/ai/draft` | 근거 기반 Q&A · 초안 생성 |
| POST | `/admin/crawl/run` · GET `/admin/crawl/runs` | 월간 크롤 수동 실행·이력 |
| POST | `/admin/index/run` | 임베딩 인덱싱 |
| GET | `/health` | 헬스체크 |

## 데이터 구조 요약
- `stores` × `store_offers` — 편의점·카페·음식점·마트·베이커리·H&B 매장과 결제수단별 할인. `category`로 지도 필터링한다.
- `local_benefit_merchants` — 학생제휴 33건, 온누리 40건, 서울Pay+·제로페이 1,140건. 원본 주소·혜택·학생인증 조건을 보존하고 Kakao 주소/장소검색으로 지도 좌표를 표시한다.
- `cards` × `card_benefits` — **브랜드 단위** 카드 혜택. 매장마다 복제하지 않고 `brand_key`로 조인한다
  (`이마트24 생협` → `이마트24`). 카드 혜택 다수가 `간편결제 제외` 조건이므로 API가 더 유리한 쪽을 `best_deal`로 추천한다.
- `scholarships` — 실제 크롤링 공고 또는 로컬 데모용 `sample` 공고.
- `user_applications` × `application_documents` — 과거·생성 신청서(문항 단위). 쓸수록 초안 품질이 오르는 플라이휠.
- `users` — 공통 프로필 테이블. 현재 프론트 프로필은 `localStorage(paypick.profile.v1)`로 관리한다.

## 월간 크롤링 파이프라인
매월 1일 04:00 KST에 APScheduler가 실행한다: 만료 공고 `closed` → 당월+익월 크롤 →
`content_key` 멱등 upsert → `CrawlRun` 이력 기록. 현재 경희대 장학공지와 드림스폰이 실제 동작하며,
온통청년은 API 키 승인 후 연동 예정이다.

## 미구현/후속(TODO)
- 청년정책 API 연동 및 무용한 KOSAF 보관뉴스 크롤러 교체
- 매장별·기간별 실제 프로모션 데이터 수집(현재 간편결제 시드는 동일 할인율 예시)
- 사용자 인증과 localStorage 프로필의 서버 이전
- Alembic 마이그레이션, 마감 리마인더 알림
- 관리형 PostgreSQL + pgvector 배포 구성
