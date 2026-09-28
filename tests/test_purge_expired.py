"""마감 공고 삭제: 마감일이 지난 것만 지우고, 참조는 정리한다."""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.crawlers.registry import purge_expired_postings
from app.models.application import ApplicationSource, UserApplication
from app.models.scholarship import Scholarship, ScholarshipEmbedding
from tests.conftest import KST, make_scholarship


def test_purge_deletes_only_past_deadlines_and_detaches_refs(db):
    now = datetime.now(KST)
    past = make_scholarship(title="끝남", deadline_at=now - timedelta(hours=1))
    future = make_scholarship(title="진행중", deadline_at=now + timedelta(days=3))
    undated = make_scholarship(title="상시", deadline_at=None)
    db.add_all([past, future, undated])
    db.flush()
    db.add(ScholarshipEmbedding(
        scholarship_id=past.id, chunk_type="body", chunk_text="x",
        embedding=[0.0] * settings.embedding_dim,
    ))
    application = UserApplication(
        user_id=uuid.uuid4(), scholarship_name="끝남",
        scholarship_id=past.id, source=ApplicationSource.GENERATED,
    )
    db.add(application)
    db.commit()

    assert purge_expired_postings(db) == 1

    db.expire_all()
    assert set(db.scalars(select(Scholarship.title))) == {"진행중", "상시"}
    assert db.scalar(select(ScholarshipEmbedding.id)) is None
    kept = db.get(UserApplication, application.id)
    assert kept.scholarship_name == "끝남" and kept.scholarship_id is None
