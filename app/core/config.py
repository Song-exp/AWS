"""애플리케이션 설정. 환경변수(.env)에서 로드한다."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_env: str = "development"          # development | production
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # 프론트 오리진(쉼표 구분). 운영에서는 실제 도메인만 허용해야 한다.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # /admin/* 보호용 토큰. 요청 헤더 X-Admin-Token 과 대조한다.
    # 비어 있으면 운영 모드 부팅이 실패한다(아래 _require_production_settings).
    admin_token: str = ""

    # --- 로그인 세션 ---
    session_cookie_name: str = "benefit_session"
    session_ttl_days: int = 30
    # HTTPS 전용 전송. 운영에서 false면 쿠키가 평문으로 오간다.
    session_cookie_secure: bool = False
    # lax: 다른 사이트에서 넘어온 POST에 쿠키가 실리지 않아 CSRF를 막는다.
    # 프론트와 API가 다른 도메인이면 쿠키가 아예 안 실리므로, 같은 도메인
    # 아래에서 /api 를 백엔드로 라우팅하는 배포(개발의 Vite 프록시와 동일한
    # 구조)를 전제한다. 도메인을 분리해야 하면 none + secure 로 바꾸고
    # CSRF 토큰을 별도로 도입해야 한다.
    session_cookie_samesite: str = "lax"

    # scrypt 비용. 클수록 안전하지만 로그인 응답이 느려진다(동기 처리).
    # 2**15 ≈ 110ms. OWASP 최소 권장은 2**14.
    scrypt_n: int = 32768

    # 로그인·가입 시도 분당 상한(IP 기준). 무차별 대입 방어.
    auth_rate_limit_per_min: int = 10

    # --- 커뮤니티 ---
    # HOT/BEST 게시판 편입 기준(공감 수). 커뮤니티가 커지면 올려야 한다.
    community_hot_like_threshold: int = 10
    community_best_like_threshold: int = 50
    # 내 글에 이만큼 신고가 쌓이면 등급을 한 단계 내린다. 0이면 강등 없음.
    community_report_demote_threshold: int = 5

    # --- 끝난 혜택 제보 ---
    # 이 수 이상 제보되면 지도에서 흐리게 표시하고 best_deal 추천에서 뺀다.
    # 자동 비활성은 하지 않는다. 오탭 몇 번, 경쟁 매장 몇 번이면 정상 혜택이
    # 사라지기 때문에 마지막 판단은 사람이 한다(GET /admin/offer-reports).
    store_offer_report_threshold: int = 3

    # --- 마감 리마인더 ---
    # 매일 09:00 KST에 D-N 공고를 메일로 알린다. SMTP 미설정이면 로그로만 나간다.
    deadline_reminder_enabled: bool = True
    deadline_reminder_hour: int = 9      # KST
    # 마감 며칠 전에 보낼지(쉼표 구분). 너무 많이 보내면 스팸이 된다.
    deadline_reminder_days: str = "7,3,1"

    # --- 비밀번호 재설정 ---
    # 재설정 링크에 쓸 프론트 주소. 메일에 들어가므로 실제 접속 가능한 값이어야 한다.
    app_base_url: str = "http://localhost:5173"
    # 링크 수명. 짧을수록 안전하지만 메일 확인이 늦은 사용자가 놓친다.
    password_reset_ttl_minutes: int = 30

    # --- SMTP (stdlib smtplib) ---
    # 비우면 메일을 보내지 않고 로그로 출력한다(로컬 개발용).
    # 운영 모드에서는 비어 있으면 부팅이 실패한다.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True    # 587: STARTTLS
    smtp_use_ssl: bool = False   # 465: 처음부터 TLS

    # Database
    # 로컬 개발 기본값은 SQLite. 운영/배포 시 DATABASE_URL을 PostgreSQL로 지정하면
    # pgvector 기반 벡터 검색까지 활성화된다.
    database_url: str = "sqlite:///./data/app.db"

    # LLM (DeepSeek: OpenAI 호환, base_url만 교체)
    deepseek_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    # 외부 LLM 호출은 사용자 요청 시간에 그대로 물린다. 반드시 상한을 둔다.
    llm_timeout_sec: float = 20.0
    llm_max_retries: int = 2

    # /chat/* 분당 호출 상한(클라이언트 IP 기준). LLM 비용 폭주 방지.
    chat_rate_limit_per_min: int = 20

    # Embeddings (DeepSeek는 임베딩 미지원 → 로컬 해시 기반 폴백)
    # 실제 임베딩 모델 도입 시 embedding_dim을 그 모델 차원에 맞춰 조정.
    embedding_dim: int = 256

    # Uploads
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 10

    # Crawling (일간 파이프라인)
    crawl_respect_robots: bool = True
    crawl_default_delay_sec: float = 1.5
    # 온통청년 청년정책 Open API 키. 비우면 해당 소스는 건너뛴다.
    youthcenter_api_key: str = ""

    # 일간 스케줄러 (매일 00:10 KST: 날짜가 바뀐 직후 마감 삭제 + 신규 수집)
    # ponytail: 인스턴스 내부 APScheduler라 리더 선출이 없다. 웹 인스턴스를 2대
    # 이상 띄우면 크롤이 중복 실행되므로, 스케줄러 전용 인스턴스 1대에서만
    # true로 두고 나머지는 false로 배포한다. 상시 다중화가 필요해지면
    # DB 어드바이저리 락이나 별도 워커(EventBridge/Cron)로 승격.
    crawl_schedule_enabled: bool = True
    crawl_schedule_hour: int = 0         # KST 시각
    crawl_schedule_minute: int = 10


    @property
    def reminder_day_list(self) -> list[int]:
        days = []
        for part in self.deadline_reminder_days.split(","):
            part = part.strip()
            if part.isdigit():
                days.append(int(part))
        return sorted(set(days), reverse=True)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def _require_production_settings(s: "Settings") -> None:
    """운영 모드에서 빠진 필수값은 부팅 실패로 드러낸다.

    조용히 폴백하면 '배포는 됐는데 챗봇이 규칙기반으로만 답하는' 상태를
    아무도 모른 채 서비스하게 된다. 그래서 켜지지 않는 쪽을 택한다.
    """
    if not s.is_production:
        return
    missing: list[str] = []
    if not s.deepseek_api_key:
        missing.append("DEEPSEEK_API_KEY")
    if not s.admin_token:
        missing.append("ADMIN_TOKEN")
    if not s.session_cookie_secure:
        missing.append("SESSION_COOKIE_SECURE=true(HTTPS 전용 쿠키)")
    if not s.smtp_host:
        missing.append("SMTP_HOST(비밀번호 재설정 메일 발송)")
    if s.app_base_url.startswith(("http://localhost", "http://127.0.0.1")):
        missing.append("APP_BASE_URL(재설정 링크에 들어갈 실제 주소)")
    if s.database_url.startswith("sqlite"):
        missing.append("DATABASE_URL(PostgreSQL 필요)")
    if any(o.startswith(("http://localhost", "http://127.0.0.1")) for o in s.cors_origin_list):
        missing.append("CORS_ORIGINS(localhost 제거 후 실제 도메인 지정)")
    if missing:
        raise RuntimeError(
            "APP_ENV=production 인데 필수 설정이 없습니다: " + ", ".join(missing)
        )


settings = Settings()
_require_production_settings(settings)
