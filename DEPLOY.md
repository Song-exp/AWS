# 배포 세팅

작성일: 2026-09-28

프론트는 Vercel, 백엔드는 서버 1대, DB는 Supabase를 쓴다. 로컬에서 되던 기능이
코드 수정 없이 그대로 동작하는 것을 기준으로 골랐다.

수업에서 AWS 사용이 필수라면 서버만 EC2로 바꾸고 나머지는 동일하다.

## 1. 스택

| 계층 | 선택 | 설정 | 월 비용 |
|---|---|---|---|
| 프론트엔드 | Vercel 무료 플랜 | Root Directory `frontend`, `/api` 리라이트, 카카오 지도 키 | 0원 |
| 백엔드 서버 | 네이버 클라우드 Micro, Ubuntu | Docker Compose, 스왑 2GB, ACG에서 22·80·443 개방 | 1년간 0원 |
| 공인 IP·스토리지 | 네이버 클라우드 | 서버 무료 혜택에 미포함 | 크레딧으로 충당 |
| 웹 서버 | Caddy | DuckDNS 무료 도메인, 인증서 자동 발급 | 0원 |
| 앱 | FastAPI + uvicorn | 워커 1개, `APP_ENV=production`, 내부 스케줄러 | 없음 |
| DB | Supabase 무료 플랜, 서울 리전 | Session pooler 주소, pgvector | 0원 |
| 파일 저장 | 서버 디스크 | Docker 볼륨 `uploads` | 없음 |
| 메일 | Gmail SMTP | 앱 비밀번호 | 0원 |
| LLM | DeepSeek | 기존 키 | 사용량만큼 |

고정 지출은 DeepSeek 사용료뿐이다.

### 크레딧

| 종류 | 금액 | 유효기간 | 조건 |
|---|---|---|---|
| 네이버 클라우드 신규 가입 | 10만 원 | 3개월 | 신규 가입 |
| Green Rookie | 20만 원 | 1년 | 제휴 교육기관 재학생, 학교 메일로 신청 |

두 크레딧은 중복으로 받을 수 있다.

## 2. 이 구성을 고른 이유

백엔드는 프로세스가 계속 살아 있는 것을 전제로 짜여 있어 서버리스에 올릴 수 없다.

| 로컬 기능 | 전제 | 배포에서 |
|---|---|---|
| 자정 크롤, 마감 리마인더 | 앱 내부 스케줄러 | 서버가 항상 켜져 있어 그대로 실행 |
| 챗봇 대화 상태 | 프로세스 메모리 | 워커 1개로 고정 |
| 서류·게시글 이미지 업로드 | 로컬 디스크 | Docker 볼륨으로 보존 |
| Vite 프록시의 `/api` 전달 | 같은 출처 | Vercel 리라이트가 같은 역할, 쿠키 설정 변경 불필요 |
| SQLite | 파일 DB | `DATABASE_URL`만 교체 |
| 메일이 로그로만 출력 | SMTP 미설정 | 운영 모드는 SMTP 없으면 부팅 실패, Gmail SMTP 필수 |

## 3. 준비된 파일

| 파일 | 내용 |
|---|---|
| `Dockerfile` | 백엔드 이미지. 시작 시 `alembic upgrade head` 후 uvicorn 실행 |
| `docker-compose.yml` | 백엔드와 Caddy, 볼륨 `uploads`·`caddy_data` |
| `Caddyfile` | `DOMAIN` 환경변수의 도메인으로 HTTPS, 백엔드로 프록시 |
| `.dockerignore` | 가상환경, 프론트엔드, DB 파일, 환경변수 파일 제외 |
| `frontend/vercel.json` | `/api` 리라이트. `BACKEND_DOMAIN`을 실제 도메인으로 교체해야 함 |
| `requirements.txt` | 쓰지 않는 scrapy, playwright 제거 |
| `migrations/versions/55aebbb81c21_initial_schema.py` | PostgreSQL에서 pgvector 확장을 먼저 생성 |

## 4. 환경변수

### 서버의 `.env`

저장소에 올리지 않는다. 서버에서 직접 작성한다.

```
DOMAIN=<백엔드 도메인>.duckdns.org

APP_ENV=production
DATABASE_URL=postgresql+psycopg://postgres.<프로젝트ID>:<비밀번호>@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres
CORS_ORIGINS=https://<프로젝트>.vercel.app
APP_BASE_URL=https://<프로젝트>.vercel.app
SESSION_COOKIE_SECURE=true
ADMIN_TOKEN=<긴 임의 문자열>
SECRET_KEY=<32자 이상 임의 문자열>
DEEPSEEK_API_KEY=<기존 키>
YOUTHCENTER_API_KEY=<기존 키>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<Gmail 주소>
SMTP_PASSWORD=<앱 비밀번호>
CRAWL_SCHEDULE_ENABLED=true
```

`UPLOAD_DIR`은 Compose 파일이 `/srv/uploads`로 지정하므로 넣지 않는다.

관리자 토큰과 서명 키 생성. 두 값은 서로 다르게 만든다.

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`SECRET_KEY`는 이메일 인증과 수신 거부 링크를 서명한다. 바꾸면 이미 보낸 링크는 모두 무효가 된다.

### Vercel

| 변수 | 값 |
|---|---|
| `VITE_KAKAO_MAP_KEY` | 카카오 지도 JavaScript 키 |
| `VITE_API_BASE` | 비워 둔다 |

## 5. 체크리스트

### 계정과 외부 서비스

- [ ] 수업에서 AWS 배포가 필수인지 확인
- [ ] 네이버 클라우드 가입, 신규 크레딧과 Green Rookie 신청
- [ ] Ubuntu Micro 서버 생성, 공인 IP 할당
- [ ] ACG에서 22, 80, 443 포트 개방
- [ ] DuckDNS 서브도메인 생성, 서버 공인 IP 연결
- [ ] Supabase 프로젝트 생성(서울 리전), DB 비밀번호는 영문과 숫자만
- [ ] Supabase Session pooler 주소 복사
- [ ] Gmail 2단계 인증 설정, 앱 비밀번호 발급

### 코드

- [ ] `frontend/public/privacy.html`의 표시된 네 곳 채우기: 시행일, 운영자 이름, 보호책임자 이름, 문의 이메일
- [ ] 처리방침의 위탁 업체 표가 실제 구성과 같은지 확인
- [ ] 간편결제 혜택을 실제 값으로 교체. 교체 전에는 화면에 예시로 표시된다
- [ ] `frontend/vercel.json`의 `BACKEND_DOMAIN`을 백엔드 도메인으로 교체
- [ ] 배포 파일 커밋 후 push

### 서버

```bash
# 스왑(이미지 빌드 중 메모리 부족 방지)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

curl -fsSL https://get.docker.com | sudo sh
git clone <저장소 주소> app && cd app
nano .env
sudo docker compose up -d --build

# 최초 1회: 시드와 크롤
sudo docker compose exec backend python -m app.scripts.init_all --scholarships crawl

curl https://<백엔드 도메인>/ready
```

코드 갱신:

```bash
git pull && sudo docker compose up -d --build
```

### Vercel과 카카오

- [ ] Vercel에 GitHub 저장소 연결, Root Directory를 `frontend`로 지정
- [ ] Vercel 환경변수에 `VITE_KAKAO_MAP_KEY` 입력
- [ ] 카카오 개발자 콘솔의 플랫폼에 Vercel 도메인 등록

### 배포 후 점검

- [ ] 회원가입, 로그인, 로그아웃
- [ ] 비밀번호 재설정 메일 수신
- [ ] 챗봇 대화
- [ ] 서류 업로드와 게시글 이미지 업로드. 10MB에 가까운 파일로도 시험
- [ ] 지도 표시
- [ ] 가입 시 동의 체크 없이는 가입이 막히는지
- [ ] 인증 메일 수신, 링크 클릭 후 마이페이지에 인증 완료 반영
- [ ] 마이페이지에서 알림 켜기와 끄기
- [ ] 관리자 크롤 수동 실행 `POST /admin/crawl/run`
- [ ] 신고 목록 조회 `GET /admin/moderation/reports`
- [ ] 로그인을 여러 번 틀리면 429가 나오는지
- [ ] 로그인하지 않은 상태에서 `POST /ai/qa` 가 401인지
- [ ] 다음 날 자정 크롤 이력 확인 `GET /admin/crawl/runs`

## 6. 운영

### 신고 처리

관리자 화면은 없다. 아래 API를 `X-Admin-Token` 헤더와 함께 호출한다.
자동 숨김은 하지 않으므로 이 목록을 주기적으로 확인해야 한다.

| 할 일 | 요청 |
|---|---|
| 신고된 글·댓글 보기 | `GET /admin/moderation/reports` |
| 글 삭제 | `DELETE /admin/moderation/posts/{id}` |
| 댓글 삭제 | `DELETE /admin/moderation/comments/{id}` |
| 신고 기각 | `DELETE /admin/moderation/posts/{id}/reports` 또는 `comments` |

```bash
curl -H "X-Admin-Token: $ADMIN_TOKEN" https://<백엔드 도메인>/admin/moderation/reports
```

### 간편결제 혜택을 실제 값으로 바꾸기

시드가 넣는 간편결제 혜택은 전 매장 동일한 예시 값이라 `is_sample`이 켜져 있다.
실제 프로모션을 확인하면 `store_offers`의 할인율과 조건을 고치고 `is_sample`을 끈다.
끈 혜택은 시드를 다시 돌려도 덮어쓰지 않는다.

### 그 밖에

- **백업:** Supabase 무료 플랜에는 백업이 없다. 주 1회 DB 덤프와 업로드 볼륨 백업을 직접 건다.
- **Supabase 자동 정지:** 7일간 쿼리가 없으면 정지된다. 백엔드가 켜져 있으면 매일 크롤이 돌아 해당되지 않는다.
- **Micro 서버 만료:** 생성 1년 뒤 반납하지 않으면 자동으로 유료 전환된다. 만료일을 기록해 둔다.
- **Vercel 무료 플랜:** 비상업용으로만 쓸 수 있다.
- **스케일아웃:** 인스턴스를 늘리려면 세션, 업로드, 스케줄러 분리가 먼저다. README의 해당 절 참고.

## 7. 알려진 제약과 미확인 사항

### 의도적으로 단순화한 부분

챗봇 세션은 서버 메모리에 있고 6시간 동안 쓰지 않으면 지워진다. 동시에 2,000개까지만 둔다.
서버를 재시작하면 진행 중이던 대화는 사라진다.

Caddy가 `X-Forwarded-For`를 실제 접속 IP로 덮어쓴다. 클라이언트가 보낸 값을 믿으면
헤더 한 줄로 호출 상한이 사라진다. 그래서 Vercel을 거친 요청은 모두 Vercel 엣지 IP로
보인다. IP 기준 상한이 엣지 단위로 걸릴 수 있어, 로그인은 계정 기준 상한이 함께 막는다.

호출 상한 카운터는 프로세스 메모리에 있다. 인스턴스를 늘리면 실효 상한이 그만큼 늘어난다.
서버 1대 구성에서는 문제가 없다.

### 검증하지 못한 것

| 항목 | 확인 방법 |
|---|---|
| Docker 이미지 빌드 | 서버에서 첫 `docker compose up` |
| Caddy 설정과 인증서 발급 | 서버에서 첫 실행 후 `/ready` 호출 |
| 빈 PostgreSQL에서의 마이그레이션 | 컨테이너 첫 시작 로그 |
| Vercel 리라이트의 업로드 용량 제한 | 배포 후 큰 파일 업로드 시험 |
| Micro 서버 사양, 공인 IP 단가 | 네이버 클라우드 요금표 |
| 경희대의 Green Rookie 제휴 여부 | 학교 메일로 신청 |

업로드가 Vercel에서 막히면 프론트엔드도 같은 서버의 Caddy로 서빙하는 구성으로 바꾼다.

### 로컬 빌드

로컬의 `frontend/dist` 폴더로 빌드하면 네이티브 오류로 종료된다. 다른 출력 폴더로는 정상
빌드되므로 그 폴더만의 문제이고 Vercel 배포와는 무관하다.
