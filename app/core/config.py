"""애플리케이션 설정. 환경변수(.env)에서 로드한다."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database
    # 로컬 개발 기본값은 SQLite. 운영/배포 시 DATABASE_URL을 PostgreSQL로 지정하면
    # pgvector 기반 벡터 검색까지 활성화된다.
    database_url: str = "sqlite:///./data/app.db"

    # LLM (DeepSeek: OpenAI 호환, base_url만 교체)
    deepseek_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    # Embeddings (DeepSeek는 임베딩 미지원 → 로컬 해시 기반 폴백)
    # 실제 임베딩 모델 도입 시 embedding_dim을 그 모델 차원에 맞춰 조정.
    embedding_dim: int = 256

    # Uploads
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 10

    # Crawling (월간 파이프라인: 당월 + N개월 후까지 수집)
    crawl_months_ahead: int = 1          # 당월 + 익월
    crawl_respect_robots: bool = True
    crawl_default_delay_sec: float = 1.5

    # 월간 스케줄러 (매월 1일 04:00 KST 기본)
    crawl_schedule_enabled: bool = True
    crawl_schedule_day: int = 1          # 매월 며칠
    crawl_schedule_hour: int = 4         # KST 시각
    crawl_schedule_minute: int = 0


settings = Settings()
