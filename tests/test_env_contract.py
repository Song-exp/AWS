"""설정 문서와 코드가 어긋나지 않는지 검증.

.env.example 은 배포하는 사람이 읽는 유일한 설정 명세다. 코드에 설정을
추가하고 여기를 안 고치면, 배포자는 그 값이 있는 줄도 모른 채 기본값으로
운영하게 된다. 그래서 드리프트를 테스트로 막는다.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.core.config import Settings

_ROOT = Path(__file__).resolve().parents[1]
_KEY = re.compile(r"^([A-Z][A-Z0-9_]*)=", re.MULTILINE)


def _documented_keys() -> set[str]:
    text = (_ROOT / ".env.example").read_text(encoding="utf-8")
    return set(_KEY.findall(text))


def _settings_keys() -> set[str]:
    return {name.upper() for name in Settings.model_fields}


def test_every_setting_is_documented():
    missing = _settings_keys() - _documented_keys()
    assert not missing, f".env.example 에 빠진 설정: {sorted(missing)}"


def test_no_stale_keys_in_env_example():
    stale = _documented_keys() - _settings_keys()
    assert not stale, f"코드에 없는데 .env.example 에 남은 설정: {sorted(stale)}"


def test_env_example_is_not_a_secret_leak():
    """예시 파일에 실제 키가 커밋되는 사고를 막는다."""
    text = (_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            value = line.split("=", 1)[1].strip()
            assert not value.startswith("sk-") or "your-key" in value, (
                "실제 DeepSeek 키가 .env.example 에 들어 있다"
            )


def test_real_env_is_gitignored():
    """.env 가 추적되면 키가 그대로 공개된다."""
    ignored = (_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^\.env$", ignored, re.MULTILINE)


def test_alembic_migration_exists():
    """운영은 create_all 이 아니라 마이그레이션으로 스키마를 만든다.

    리비전이 없으면 첫 배포에서 테이블이 하나도 생기지 않는다.
    """
    versions = list((_ROOT / "migrations" / "versions").glob("*.py"))
    assert versions, "migrations/versions 에 리비전이 없다"


def test_migration_matches_models():
    """모델을 고치고 마이그레이션을 안 만들면 배포 DB만 옛 스키마로 남는다.

    빈 임시 DB에 마이그레이션을 올린 뒤, 모델 메타데이터와 비교해
    미반영 변경이 있으면 실패시킨다.
    """
    import tempfile
    from pathlib import Path as _P

    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    import app.models  # noqa: F401
    from app.core.db import Base

    tmp = _P(tempfile.mkdtemp(prefix="alembic_check_")) / "chk.db"
    url = f"sqlite:///{tmp.as_posix()}"

    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        diff = compare_metadata(ctx, Base.metadata)

    # alembic_version 테이블은 비교 대상이 아니다
    diff = [d for d in diff if "alembic_version" not in str(d)]
    assert not diff, f"모델과 마이그레이션이 다르다. 새 리비전이 필요하다:\n{diff}"
