"""방언 독립 컬럼 타입.

운영은 PostgreSQL(JSONB/ARRAY/UUID/pgvector), 로컬 개발은 SQLite를 쓴다.
DATABASE_URL만 바꾸면 동일 모델 코드가 양쪽에서 동작하도록 타입을 감싼다.

- JSONType   : JSONB(PG) / JSON(SQLite)
- StrListType: ARRAY(String)(PG) / JSON(SQLite)
- GUIDType   : UUID(PG) / CHAR(36)(SQLite)  — 파이썬 측은 uuid.UUID로 통일
- vector_column(dim): Vector(PG) / JSON(SQLite)
"""
from __future__ import annotations

import uuid

from sqlalchemy import CHAR, JSON, BigInteger, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, TypeEngine

from app.core.config import settings


def is_postgres() -> bool:
    return settings.database_url.startswith("postgresql")


def supports_vector_search() -> bool:
    """DB가 벡터 유사도 검색(pgvector)을 지원하는지."""
    return is_postgres()


# 자동증가 PK: SQLite는 INTEGER PRIMARY KEY만 rowid 자동증가로 인식하므로
# BIGINT를 쓰면 id가 NULL이 된다. 방언별로 타입을 바꿔준다.
PKType = BigInteger().with_variant(Integer(), "sqlite")


# --- JSON 계열: 방언에 따라 구현 교체 ---
JSONType = JSON().with_variant(JSONB(), "postgresql")

# 문자열 배열: PG는 native ARRAY, 그 외는 JSON
StrListType = JSON().with_variant(ARRAY(String), "postgresql")


class GUIDType(TypeDecorator):
    """UUID를 PG에서는 native UUID, 그 외에는 CHAR(36)으로 저장."""

    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def vector_column(dim: int) -> TypeEngine:
    """방언에 맞는 임베딩 벡터 컬럼 타입."""
    if is_postgres():
        from pgvector.sqlalchemy import Vector

        return Vector(dim)
    return JSON()
