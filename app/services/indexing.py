"""임베딩 인덱싱 배치.

- 사용자 업로드/생성 문서(ApplicationDocument)를 청킹·임베딩해
  DocumentEmbedding에 적재하고 embedding_status=indexed로 갱신.
- 크롤링 공고(Scholarship)를 청크 타입별로 임베딩해 ScholarshipEmbedding에 적재.

임베딩은 services.llm.embed_texts(로컬 해시 폴백 또는 실제 모델)를 사용한다.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import ApplicationDocument, DocumentEmbedding
from app.models.scholarship import Scholarship, ScholarshipEmbedding
from app.services import llm
from app.utils.pii import mask_pii

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 500  # 문자 단위 청크 크기
_CHUNK_OVERLAP = 50


def chunk_text(text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """문자 기반 슬라이딩 윈도우 청킹. 빈 텍스트는 빈 리스트."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    step = max(size - overlap, 1)
    while start < len(text):
        chunks.append(text[start : start + size])
        start += step
    return chunks


def index_documents(db: Session, limit: int = 100) -> int:
    """embedding_status=pending인 문서를 임베딩·적재. 처리한 문서 수 반환."""
    docs = db.scalars(
        select(ApplicationDocument)
        .where(ApplicationDocument.embedding_status == "pending")
        .limit(limit)
    ).all()

    processed = 0
    for doc in docs:
        # PII 마스킹 후 청킹 → 임베딩
        safe = mask_pii(doc.content_text)
        chunks = chunk_text(safe)
        if chunks:
            vectors = llm.embed_texts(chunks)
            for ch, vec in zip(chunks, vectors):
                db.add(DocumentEmbedding(document_id=doc.id, chunk_text=ch, embedding=vec))
        doc.embedding_status = "indexed"
        processed += 1

    db.commit()
    return processed


def _scholarship_chunks(s: Scholarship) -> list[tuple[str, str]]:
    """공고를 (chunk_type, text) 쌍으로 분해."""
    pairs: list[tuple[str, str]] = []
    if s.eligibility:
        pairs.append(("eligibility", str(s.eligibility)))
    if s.benefit:
        pairs.append(("benefit", str(s.benefit)))
    if s.required_documents:
        pairs.append(("documents", ", ".join(s.required_documents)))
    if s.body_text:
        for ch in chunk_text(s.body_text):
            pairs.append(("body", ch))
    return pairs


def index_scholarships(db: Session, limit: int = 100) -> int:
    """임베딩이 아직 없는 공고를 임베딩·적재. 처리한 공고 수 반환."""
    # 임베딩이 하나도 없는 공고만 대상(간이 조건)
    scholarships = db.scalars(
        select(Scholarship)
        .where(~Scholarship.embeddings.any())
        .limit(limit)
    ).all()

    processed = 0
    for s in scholarships:
        pairs = _scholarship_chunks(s)
        if pairs:
            texts = [t for _, t in pairs]
            vectors = llm.embed_texts(texts)
            for (ctype, ctext), vec in zip(pairs, vectors):
                db.add(
                    ScholarshipEmbedding(
                        scholarship_id=s.id,
                        chunk_type=ctype,
                        chunk_text=ctext,
                        embedding=vec,
                    )
                )
        processed += 1

    db.commit()
    return processed


def reindex_all(db: Session) -> dict:
    """문서 + 공고 인덱싱을 한 번에 수행."""
    docs = index_documents(db)
    schs = index_scholarships(db)
    return {"documents_indexed": docs, "scholarships_indexed": schs}


def search_user_document_chunks(
    db: Session, user_id, query: str, top_k: int = 5
) -> list[str]:
    """사용자의 과거 답변 청크 중 query와 가장 유사한 것들을 반환(pgvector).

    초안 생성 시 관련 있는 과거 답변만 컨텍스트로 넣기 위한 용도.
    """
    from app.models.application import UserApplication
    from app.core.types import supports_vector_search

    base = (
        select(DocumentEmbedding.chunk_text)
        .join(ApplicationDocument, DocumentEmbedding.document_id == ApplicationDocument.id)
        .join(UserApplication, ApplicationDocument.application_id == UserApplication.id)
        .where(
            UserApplication.user_id == user_id,
            UserApplication.is_reusable.is_(True),
        )
    )

    if not supports_vector_search():
        # SQLite 등: DB 벡터 연산 미지원 → 최신 청크 일부를 그대로 반환(폴백)
        return list(db.scalars(base.limit(top_k)).all())

    qvec = llm.embed_text(query)
    stmt = base.order_by(DocumentEmbedding.embedding.cosine_distance(qvec)).limit(top_k)
    return list(db.scalars(stmt).all())
