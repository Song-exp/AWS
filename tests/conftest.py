"""테스트 하네스 공통 설정.

원칙:
  - 실제 개발 DB(data/app.db)를 절대 건드리지 않는다. 세션마다 임시 SQLite를 쓴다.
  - 외부 통신을 하지 않는다. LLM 키를 비워 규칙기반 폴백 경로로 고정한다.
  - 시드 스크립트(수천 건)를 돌리지 않는다. 검증에 필요한 최소 데이터만 넣는다.

주의: app.core.db 는 import 시점에 settings.database_url 로 엔진을 만든다.
그래서 환경변수는 app.* 를 import 하기 **전에** 세팅해야 한다. conftest 는
테스트 모듈보다 먼저 import 되므로 이 파일 최상단이 유일하게 안전한 위치다.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="benefit_tests_"))

# 기본은 임시 SQLite. CI에서 TEST_DATABASE_URL 로 PostgreSQL을 지정하면
# 같은 하네스가 운영 방언으로 한 번 더 돈다. 로컬만 검증하면
# JSONB/ARRAY/UUID/pgvector 차이를 배포 후에야 발견하게 된다.
#   예) TEST_DATABASE_URL=postgresql+psycopg://u:p@localhost:5432/test pytest -q
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", f"sqlite:///{(_TMP / 'test.db').as_posix()}"
)
os.environ["DEEPSEEK_API_KEY"] = ""            # LLM 호출 없이 폴백 경로 검증
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ["CRAWL_SCHEDULE_ENABLED"] = "false"  # 테스트 중 크롤 스케줄러 금지
os.environ["APP_ENV"] = "development"

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.models.card import BenefitType, Card, CardBenefit, Confidence  # noqa: E402
from app.models.scholarship import (  # noqa: E402
    Category,
    PostingStatus,
    Scholarship,
    SourceType,
)
from app.models.store import PayMethod, Store, StoreCategory, StoreOffer  # noqa: E402

ADMIN_TOKEN = "test-admin-token"
KST = timezone(timedelta(hours=9))


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _clean(_schema):
    """테스트마다 빈 DB에서 시작한다(순서 의존 제거)."""
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    from app.core.security import _reset_rate_limit

    _reset_rate_limit()
    yield


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture()
def auth_client(client: TestClient) -> TestClient:
    """가입까지 마쳐 세션 쿠키를 들고 있는 클라이언트.

    개인 데이터 엔드포인트는 전부 로그인을 요구하므로, 그쪽 테스트는
    이 픽스처를 쓴다. 비로그인 차단 자체는 test_authorization.py 가 검증한다.
    """
    r = client.post(
        "/auth/signup",
        json={"email": "tester@khu.ac.kr", "password": "test-password-1"},
    )
    assert r.status_code == 201, r.text
    return client


# ---------------- 시드 헬퍼 ----------------
@pytest.fixture()
def seed_stores(db):
    """경희대 근처 매장 2곳 + 먼 매장 1곳.

    - CU 경희대점: 카카오 10% (간편결제 우세)
    - GS25 회기점: 네이버 5% + 카드 20% (카드 우세)
    - CU 부산점  : 반경 밖(거리 필터 검증용)
    """
    near = Store(brand="CU", branch="경희대점", category=StoreCategory.CONVENIENCE,
                 lat=37.5966, lng=127.0525, mark="CU", color="#7b2cbf")
    near.offers.append(StoreOffer(pay_method=PayMethod.KAKAO, discount_rate=10,
                                  condition_text="1만원 이상"))

    mid = Store(brand="GS25", branch="회기점", category=StoreCategory.CONVENIENCE,
                lat=37.5900, lng=127.0500, mark="GS", color="#00a0e9")
    mid.offers.append(StoreOffer(pay_method=PayMethod.NAVER, discount_rate=5))

    cafe = Store(brand="스타벅스", branch="경희대점", category=StoreCategory.CAFE,
                 lat=37.5970, lng=127.0530)

    far = Store(brand="CU", branch="부산서면점", category=StoreCategory.CONVENIENCE,
                lat=35.1579, lng=129.0594)

    card = Card(card_key="test-card", card_name="테스트 체크카드", issuer="테스트은행")
    card.benefits.append(
        CardBenefit(
            dedup_key="test-gs25-20",
            merchant_raw="GS25",
            brand_key="GS25",
            benefit_type=BenefitType.PERCENT,
            value_min=20.0,
            value_max=20.0,
            benefit_text="GS25 20% 청구할인",
            conditions=["간편결제 제외"],
            excludes_simple_pay=True,
            confidence=Confidence.CONFIRMED,
        )
    )
    db.add_all([near, mid, cafe, far, card])
    db.commit()
    return {"near": near.id, "mid": mid.id, "cafe": cafe.id, "far": far.id,
            "card_id": card.id}


def make_scholarship(**kw) -> Scholarship:
    """테스트용 공고. 필수 필드는 기본값을 채우고 검증 대상만 덮어쓴다."""
    now = datetime.now(KST)
    defaults = dict(
        content_key=f"key-{kw.get('title', 'x')}",
        title="테스트 장학금",
        organization="테스트재단",
        source_type=SourceType.PRIVATE,
        category=Category.SCHOLARSHIP,
        source_platform="test",
        source_url="https://example.test/1",
        deadline_at=now + timedelta(days=10),
        eligibility={},
        benefit={},
        required_documents=[],
        body_text="",
        status=PostingStatus.OPEN,
    )
    defaults.update(kw)
    return Scholarship(**defaults)
