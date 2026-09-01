"""Alembic 환경설정.

DB URL은 alembic.ini가 아니라 app.core.config(=.env)에서 가져온다.
설정 출처를 하나로 유지해야 "앱은 PG를 보는데 마이그레이션은 SQLite에
걸린" 사고가 안 난다.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.db import Base
import app.models  # noqa: F401  # 모델 등록(메타데이터 채우기)

config = context.config

# 평소에는 .env(app.core.config)가 URL의 단일 출처다. 다만 호출 측이
# sqlalchemy.url 을 명시했다면(테스트·CI가 임시 DB를 지정하는 경우) 그것을
# 존중한다. 무조건 덮어쓰면 검증용 임시 DB 대신 개발 DB를 건드리게 된다.
_url = config.get_main_option("sqlalchemy.url") or settings.database_url
config.set_main_option("sqlalchemy.url", _url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # PostgreSQL이면 pgvector 확장을 먼저 보장한다.
        if not _url.startswith("sqlite"):
            from sqlalchemy import text

            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # SQLite는 ALTER 지원이 약해 배치 모드가 필요하다.
            render_as_batch=_url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
