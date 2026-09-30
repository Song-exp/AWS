# TMI - 대학생 맞춤형 혜택·지출 최적화 솔루션

지도 할인과 장학금 챗봇을 하나로 합친 대학생 생활비 절감 플랫폼.

- **지도(TMI)**: 내 주변 편의점·카페·음식점·마트 등의 간편결제/카드 할인 비교 → **지출 방어**
- **챗봇(장학금)**: 소득분위 기반 장학금 매칭 → 초안 생성 → 아카이빙 → **수입 확보**
- **마이페이지**: 신청 기록·재사용 자기소개서·보유 카드 조회

## 구조
```text
app/                    백엔드(FastAPI)
  core/    설정 · DB세션 · 방언독립 타입(SQLite/PostgreSQL 전환)
  models/  scholarship · application · crawl_run · store · card · user
  api/     stores · meta · me · chat · scholarships · ai · applications · admin
  crawlers/ 온통청년 API · 경희대 장학공지 · 일간 파이프라인
  services/ matching · rag · chat(상태머신) · indexing · llm(DeepSeek) · scheduler
  scripts/ init_all 및 개별 데이터 시드
frontend/               프론트(React + Vite + TS)
  src/pages/ OnboardingPage · MapPage · ChatPage · CommunityPage · MyPage
             AuthPage · ResetPasswordPage · BoardListPage · BoardPage · PostDetailPage
  src/App.tsx 로그인 게이트 + 온보딩 + 하단 4탭(지도·챗봇·게시판·마이)
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
`init_all`의 장학금 모드는 `sample`(기본, 외부 통신 없음), `crawl`, `skip`이다. `crawl`은 일간 파이프라인을
한 번 실행한다(`YOUTHCENTER_API_KEY` 필요). 각 시드는 upsert 방식이라 재실행해도 중복되지 않는다.

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

### 3) 테스트
```powershell
.\.venv\Scripts\python.exe -m pytest        # 외부 통신 없음
```
`tests/`는 임시 SQLite를 만들어 돌고 개발 DB(`data/app.db`)를 건드리지 않는다.
LLM 키를 비운 채 실행되므로 **DeepSeek가 죽어도 서비스가 사는지**가 함께 검증된다.
CI에서 운영 방언까지 보려면 PostgreSQL을 지정한다:
```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/test"
.\.venv\Scripts\python.exe -m pytest
```

## 배포

### 스키마는 Alembic으로 만든다
`init_db()`(create_all)는 **개발 전용**이다(`APP_ENV=development`일 때만 실행).
운영 DB는 마이그레이션으로 만든다:
```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.scripts.init_all --scholarships crawl
```
모델을 고치면 리비전을 만든다. 빠뜨리면 `pytest`의 `test_migration_matches_models`가 실패한다.
```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "설명"
```

### 운영 필수 환경변수
`APP_ENV=production`이면 아래가 없을 때 **부팅이 실패한다.** 조용히 폴백해
반쪽짜리로 서비스되는 것보다 안 켜지는 편이 낫다는 판단이다.

| 변수 | 이유 |
|---|---|
| `DEEPSEEK_API_KEY` | 없으면 챗봇이 규칙기반으로 조용히 저하됨 |
| `ADMIN_TOKEN` | `/admin/*`(크롤·재색인 트리거) 보호. 없으면 누구나 실행 가능 |
| `SECRET_KEY` | 이메일 인증·수신 거부 링크 서명. 기본값이거나 32자 미만이면 실패 |
| `DATABASE_URL` | PostgreSQL이어야 pgvector 검색이 켜짐 |
| `CORS_ORIGINS` | localhost가 남아 있으면 실패. 실제 도메인만 허용 |
| `SESSION_COOKIE_SECURE` | `true` 여야 함. false면 세션 쿠키가 평문으로 오간다 |
| `SMTP_HOST` | 없으면 비밀번호 재설정 메일이 안 나간다(로그로만 출력됨) |
| `APP_BASE_URL` | 재설정 링크에 실리는 주소. localhost면 실패 |

### 헬스체크
| 경로 | 용도 |
|---|---|
| `/health` | liveness. 프로세스 생존만 확인 |
| `/ready` | readiness. DB 확인 후 실패 시 **503**. LLM 가용 여부도 보고 |

로드밸런서 타겟그룹은 `/ready`를 봐야 한다. `/health`만 보면 DB가 죽어도 트래픽이 계속 들어온다.

### 서버 1대 + Vercel + Supabase 배포
프론트는 Vercel, 백엔드는 서버 1대(Docker Compose: 백엔드 + Caddy), DB는 Supabase를 쓴다.

**서버** (Ubuntu 기준, 80·443 포트 개방)
```bash
# 메모리 1GB급이면 스왑부터 잡는다(이미지 빌드 중 메모리 부족 방지)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

curl -fsSL https://get.docker.com | sudo sh
git clone <저장소 주소> app && cd app
nano .env                      # 운영 필수 환경변수 + DOMAIN=<백엔드 도메인>
sudo docker compose up -d --build
sudo docker compose exec backend python -m app.scripts.init_all --scholarships crawl   # 최초 1회
curl https://<백엔드 도메인>/ready
```
컨테이너는 시작할 때마다 `alembic upgrade head`를 먼저 실행한다. 코드 갱신은
`git pull && sudo docker compose up -d --build`.

**Vercel**: Root Directory를 `frontend`로 지정하고 `VITE_KAKAO_MAP_KEY`를 넣는다.
`frontend/vercel.json`의 `BACKEND_DOMAIN`을 백엔드 도메인으로 바꿔야 `/api`가 백엔드로 전달된다.
`VITE_API_BASE`는 비워 둔다(같은 출처라 세션 쿠키 설정을 바꿀 필요가 없다).

**Supabase**: `DATABASE_URL`에는 Session pooler 주소를 쓴다(직접 연결 주소는 IPv6 전용).
`postgresql://`을 `postgresql+psycopg://`로 바꿔 넣는다.

### 인스턴스를 2대 이상 띄울 때 (미해결)
현재 코드는 **웹 인스턴스 1대 / uvicorn 워커 1개**를 전제한다.
- 챗봇 세션이 프로세스 메모리(`app/services/chat.py`의 `_SESSIONS`)에 있어 워커를 늘리면 대화가 유실된다.
- 크롤 스케줄러가 앱 안에서 돌아 인스턴스마다 중복 실행된다. 스케줄러 인스턴스 1대만 `CRAWL_SCHEDULE_ENABLED=true`로 두고 나머지는 `false`로 배포한다.
- 업로드 파일이 로컬 디스크(`UPLOAD_DIR`)에 저장돼 컨테이너 재시작 시 유실된다.

스케일아웃이 필요해지면 세션→Redis, 업로드→S3, 스케줄러→별도 워커로 분리해야 한다.

## 주요 엔드포인트
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/stores/nearby?lat=&lng=&radius_m=&pay=&card_ids=&category=&sort=` | 카테고리별 주변 매장·혜택 조회 및 최적 결제 추천 |
| GET | `/stores/local-benefits?program=&credential=&category=&offset=&limit=` | 학생제휴·온누리·서울Pay+·제로페이 가맹점 조회 |
| GET | `/stores/{id}` | 매장 상세 |
| GET | `/meta/options` | 카드·결제수단·통신사·매장 카테고리 옵션 |
| GET | `/me/summary?card_ids=` | 신청 기록·자기소개서·보유 카드 조회 (**로그인 필요**) |
| POST | `/savings/spend` · `/savings/view` · GET `/savings/summary` | 소비 완료·혜택 조회 기록, 월간 세이빙 대시보드 (**로그인 필요**) |
| GET | `/community/boards` · `/community/boards/{slug}/posts` | 게시판 목록(카테고리·검색·N뱃지) · 글 목록 |
| GET | `/community/hot` · `/community/best` · `/community/me/{posts,commented,scraps}` | HOT·BEST·내 활동 |
| POST | `/community/posts` · `/community/posts/{id}/comments` | 글쓰기 · 댓글(대댓글 1단계) |
| POST | `/community/posts/{id}/{like,scrap,report}` | 공감·스크랩·신고 토글 |
| POST | `/auth/signup` · `/auth/login` · `/auth/logout` · GET `/auth/me` | 회원가입(개인정보 동의 필수)·로그인·로그아웃·세션 확인 |
| POST | `/auth/email/verify` · `/auth/email/resend` · `/auth/reminders/unsubscribe` | 이메일 인증·인증 메일 재발송·알림 수신 거부 |
| GET | `/admin/moderation/reports` · DELETE `/admin/moderation/{posts,comments}/{id}` | 신고 목록·글과 댓글 삭제·신고 기각 (**`X-Admin-Token` 필요**) |
| PUT | `/auth/profile` | 프로필 부분 수정(온보딩 설정·매칭 조건) |
| PUT | `/auth/password` · DELETE `/auth/sessions` · POST `/auth/delete` | 비밀번호 변경·전 기기 로그아웃·회원 탈퇴 |
| POST | `/auth/password/forgot` · `/auth/password/reset` | 재설정 링크 발송·토큰으로 재설정 |
| POST | `/chat/message` | 챗봇 대화(LLM+백엔드 상태머신) |
| POST | `/chat/upload` | 대화 중 과거 신청서 첨부 |
| POST | `/scholarships/match` | 프로필 기반 장학금 매칭 |
| POST | `/applications/upload` | 과거 신청서 업로드(→텍스트 추출) |
| POST | `/applications` | 작성 신청서 저장(플라이휠) |
| POST | `/ai/qa` · `/ai/draft` | 근거 기반 Q&A · 초안 생성 |
| POST | `/admin/crawl/run` · GET `/admin/crawl/runs` | 일간 크롤(마감 삭제+신규 수집) 수동 실행·이력 (**`X-Admin-Token` 필요**) |
| POST | `/admin/index/run` | 임베딩 인덱싱 (**`X-Admin-Token` 필요**) |
| GET | `/health` | liveness(프로세스 생존) |
| GET | `/ready` | readiness(DB 확인, 실패 시 503) |

`/chat/*`는 클라이언트 IP 기준 분당 호출 상한이 걸려 있다(`CHAT_RATE_LIMIT_PER_MIN`, 기본 20).
매 호출이 유료 LLM을 태우므로 상한이 없으면 비용이 무제한이 된다.

### 인증

이메일 + 비밀번호. 세션은 **HttpOnly 쿠키**로 오가고 서버 DB(`auth_sessions`)에 남는다.

- 비밀번호: stdlib `hashlib.scrypt`(N=2¹⁵, r=8, p=1). 외부 의존성 없음
- 세션 토큰: 원문 대신 sha256 해시만 저장 → DB가 유출돼도 세션 재사용 불가
- 로그아웃은 서버에서 세션을 폐기한다(쿠키만 지우면 토큰이 계속 유효하다)
- 로그인 실패 응답은 '없는 계정'과 '틀린 비밀번호'를 구분하지 않는다(계정 열거 방지)

**로그인이 필요한 것**: `/me/*`, `/applications/*`, `/savings/*`, `/ai/draft`, `/chat/upload`
**로그인 없이 되는 것**: `/stores/*`, `/meta/*`, `/chat/message` — 지도 탐색의 진입장벽을 낮게 둔다

무차별 대입 상한(`AUTH_RATE_LIMIT_PER_MIN`)은 **비밀번호를 검사하는** 4곳
(`signup`/`login`/`password`/`delete`)에만 걸린다. `/auth/me`는 앱을 열 때마다,
`/auth/profile`은 온보딩에서 여러 번 불리므로 여기에 상한을 걸면 정상 사용자가 잠긴다.

### 계정 설정

- **프로필**: 온보딩 설정(성별·카드·통신사·결제수단·학생인증·혜택프로그램)과 매칭 조건
  (소득분위·학점·학년·지역·전공)이 모두 `users`에 저장된다. 기기를 바꿔도 유지되고,
  계정에 설정이 있으면 온보딩을 건너뛴다.
- **챗봇 조건 영속화**: 대화에서 알아낸 소득분위·학점 등이 계정에 저장된다. 대화 세션은
  프로세스 메모리라 서버 재시작 시 사라지지만, 조건은 남아 다시 묻지 않는다.
- **비밀번호 변경**: 현재 비밀번호를 확인한 뒤 **다른 기기 세션을 모두 폐기**하고 현재
  브라우저만 새 세션으로 잇는다. 바꾸는 이유가 대개 '누가 보고 있을지도 모른다'이기 때문.
- **회원 탈퇴**: 계정·신청서·자기소개서·절감기록을 실제로 삭제하고 업로드 원본 파일도
  지운다. 소프트 삭제로 남기지 않는다 — 과거 신청서에 주민번호·학번·성적이 섞여 있을 수
  있어 보관 자체가 위험이다.
- **세션 정리**: 만료·폐기된 세션 행과 쓴 재설정 토큰은 일간 스케줄러가 함께 청소한다.

### 비밀번호 재설정

메일은 stdlib `smtplib`로 보낸다. Gmail 앱 비밀번호·네이버·AWS SES·Mailgun 모두
같은 SMTP 설정으로 동작해 프로바이더 SDK가 필요 없다.

- 토큰은 **1회용**이고 기본 30분 만료. 원문 대신 sha256 해시만 저장한다
- 새로 요청하면 **이전 링크가 죽는다**. 정상 경로로 비밀번호를 바꿔도 마찬가지다
- 재설정 성공 시 **모든 세션을 폐기**한다 — 비밀번호를 잃었다는 건 계정이 남의 손에
  있었을 수 있다는 뜻이다
- `/auth/password/forgot`은 가입 여부와 무관하게 항상 204다. 응답이 갈리면 이 API가
  '이 이메일이 가입돼 있는가'를 알려주는 조회 창구가 된다. 발송 실패도 같은 이유로 삼킨다

**`SMTP_HOST`가 비어 있으면 메일을 보내지 않고 링크를 로그로 출력한다.** 메일 서버 없이
로컬에서 전체 흐름을 확인하기 위한 폴백이고, 운영 모드에서는 `SMTP_HOST`가 없으면
부팅이 실패하므로 이 폴백이 운영에 새지 않는다.

> `user_id`를 쿼리·바디로 받던 7개 지점을 전부 세션 기반으로 바꿨다. 전에는 UUID만 알면
> 남의 자기소개서를 읽고 신청서를 지울 수 있었다(`tests/test_authorization.py`가 검증).

**쿠키 도메인 전제**: `SameSite=lax`라 프론트와 API가 **같은 도메인**이어야 쿠키가 실린다
(개발의 Vite 프록시와 같은 구조로, `/api`를 백엔드로 라우팅하는 배포). 도메인을 분리하려면
`SESSION_COOKIE_SAMESITE=none` + `SECURE=true`로 바꾸고 CSRF 토큰을 따로 도입해야 한다.

## 커뮤니티(게시판)

기획서 Phase 2의 '절약 꿀팁 공유'와 '공동구매 게시판'을 담는 섹션. 하단 4번째 탭.

화면은 셋이다 — **게시판 목록**(카테고리 칩·검색·바로가기·N뱃지) → **글 목록**(질문글
가로카드·HOT 글·최신순·글쓰기) → **글 상세**(공감/댓글/스크랩·대댓글·익명 댓글 입력).
섹션 안에서만 화면 스택을 관리한다. 화면이 셋뿐이고 하단 탭이 이미 최상위
내비게이션이라, 라우터를 넣으면 탭 상태와 URL 상태를 양쪽으로 맞추는 일이 늘어난다.

### 익명 규칙 (이 도메인에서 가장 중요한 부분)

대학 커뮤니티에서 익명은 부가 기능이 아니라 사람들이 글을 쓰는 이유다. 그래서:

- 익명 글·댓글은 응답에 `author_id`를 **절대 싣지 않는다.** 내 글인지는 `is_mine` 플래그로만 알린다
- 댓글 익명 번호는 **글 단위**로 부여한다. 같은 글에서 같은 사람은 늘 `익명1`이고,
  다른 글에서는 번호가 이어지지 않는다(이어지면 동일인임이 드러난다)
- 글쓴이 본인의 댓글은 `글쓴이`로 표시하고 **번호를 소비하지 않는다**
- 게시판 정책이 사용자 선택보다 우선한다. 비밀게시판은 익명 강제, 홍보게시판은 실명 강제

### 그 외 설계

- **소프트 삭제**: 댓글이 달린 글을 통째로 지우면 남의 댓글까지 사라진다. 삭제된 댓글은
  `삭제된 댓글입니다.`로 남아 대화 흐름이 유지된다
- **대댓글 1단계까지**: 깊이가 늘면 화면에서 읽기 어렵다
- **집계 컬럼**(`like_count`/`comment_count`): 매번 `count(*)`하면 목록 조회가 글 수에 비례해 느려진다
- **신고**: 익명 커뮤니티는 신고 없이 운영할 수 없다. 같은 사람의 중복 신고는 1건으로 본다
- **HOT/BEST**: 공감 수 기준(`COMMUNITY_HOT_LIKE_THRESHOLD` / `..._BEST_...`). 커뮤니티가 커지면 올린다
- 커뮤니티는 **전부 로그인 필요**. 익명 글이라도 서버는 작성자를 알아야 신고·차단이 성립한다

기본 게시판 9개는 `python -m app.scripts.seed_boards`로 적재된다(`init_all`에 포함).

## 데이터 구조 요약
- `stores` × `store_offers` — 편의점·카페·음식점·마트·베이커리·H&B 매장과 결제수단별 할인. `category`로 지도 필터링한다.
- `local_benefit_merchants` — 학생제휴 33건, 온누리 40건, 서울Pay+·제로페이 1,140건. 원본 주소·혜택·학생인증 조건을 보존하고 Kakao 주소/장소검색으로 지도 좌표를 표시한다.
- `cards` × `card_benefits` — **브랜드 단위** 카드 혜택. 매장마다 복제하지 않고 `brand_key`로 조인한다
  (`이마트24 생협` → `이마트24`). 카드 혜택 다수가 `간편결제 제외` 조건이므로 API가 더 유리한 쪽을 `best_deal`로 추천한다.
- `scholarships` — 실제 크롤링 공고 또는 로컬 데모용 `sample` 공고.
- `user_applications` × `application_documents` — 과거·생성 신청서(문항 단위). 쓸수록 초안 품질이 오르는 플라이휠.
- `users` — 공통 프로필 테이블. 현재 프론트 프로필은 `localStorage(tmi.profile.v1)`로 관리한다.

## 일간 크롤링 파이프라인
매일 00:10 KST(날짜가 바뀐 직후)에 APScheduler가 실행한다(`CRAWL_SCHEDULE_*`, 서버 프로세스 안에서 동작).
1. 마감일이 지난 공고 삭제. 신청 이력은 공고명 스냅샷이 남고 연결만 끊긴다.
2. 온통청년 청년정책 API: 모집중 전체를 받아 upsert하고, 목록에서 빠진 정책은 삭제한다.
   신청기간 끝 날짜(상시는 사업 종료일)가 마감일이며, 신청기간구분 `0057003`(마감)은 받지 않는다.
3. 경희대 장학공지: 직전 성공 실행 이후 올라온 새 글만 본문·첨부(hwpx/hwp/pdf/docx 전부)를 받아
   DeepSeek로 마감일·자격·지급액을 뽑는다. 마감일을 못 뽑은 글은 등록 후 45일 동안만 둔다.
   본문이 이미지뿐이고 텍스트 첨부가 없으면 마감일을 알 수 없다(OCR 미적용).
4. `CrawlRun` 이력 기록. 수동 실행은 `POST /admin/crawl/run`.

## 미구현/후속(TODO)
- 매장별·기간별 실제 프로모션 데이터 수집(현재 간편결제 시드는 동일 할인율 예시)
- 관리자 화면(지금은 `/admin/*` API를 직접 호출한다)
- 이미지로만 된 공고의 OCR
- 임베딩 기반 검색(임베딩은 저장만 하고 추천은 조건 매칭으로 한다)
