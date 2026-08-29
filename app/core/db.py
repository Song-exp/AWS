"""DB 엔진 및 세션 관리.

로컬 개발은 SQLite, 운영은 PostgreSQL(+pgvector)을 사용한다.
DATABASE_URL 하나로 전환된다.
"""
from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# SQLite 파일 경로의 상위 디렉토리 보장
if _is_sqlite:
    _path = settings.database_url.replace("sqlite:///", "").lstrip("./")
    _dirname = os.path.dirname(_path)
    if _dirname:
        os.makedirs(_dirname, exist_ok=True)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    # SQLite는 기본적으로 단일 스레드 체크를 하므로 FastAPI에서 완화
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """모든 ORM 모델의 베이스."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 의존성: 요청 스코프 DB 세션."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """테이블 생성. PostgreSQL이면 pgvector 확장을 먼저 활성화한다.

    로컬(SQLite)에서는 확장 없이 바로 생성한다. 운영에서는 Alembic
    마이그레이션 사용을 권장하며, 이 함수는 개발/시드 편의용이다.
    """
    # 모델 등록(임포트 side effect로 metadata에 반영)
    import app.models  # noqa: F401

    if not _is_sqlite:
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
