"""RAG 파이프라인: Q&A(근거 제시) + 초안 생성(과거 이력 기반).

원칙:
  - 사실 조회(마감/금액/자격)는 벡터검색이 아닌 정형 DB 쿼리로 확보한다.
  - LLM은 제공된 컨텍스트 밖 사실을 생성하지 않는다(grounding 강제).
  - 근거 공고가 없으면 '확인된 공고 없음'으로 정직하게 답한다.
  - 초안은 사용자의 과거 답변 범위 내에서만 재구성한다(창작 금지).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import ApplicationDocument, UserApplication
from app.models.scholarship import Category, PostingStatus, Scholarship
from app.schemas.schemas import (
    DraftAnswer,
    DraftResponse,
    QACitation,
    QARequest,
    QAResponse,
    UserProfile,
)
from app.services import llm
from app.services.matching import match_scholarships

_QA_SYSTEM = (
    "너는 장학금 안내 어시스턴트다. 반드시 제공된 '공고 컨텍스트' 안의 정보로만 "
    "답하라. 컨텍스트에 없는 마감일·금액·자격을 절대 지어내지 마라. 근거가 없으면 "
    "'확인된 공고가 없습니다'라고 답하라. 답변에는 공고명과 마감일을 명시하라."
)

_DRAFT_SYSTEM = (
    "너는 장학금 신청서 초안 작성 도우미다. 반드시 제공된 '사용자 과거 답변'에 "
    "근거해서만 문장을 재구성하라. 과거 답변에 없는 경력·수치·사실을 새로 지어내지 "
    "마라. 근거가 부족하면 사용자가 채워야 할 부분을 [보완 필요]로 표시하라."
)


def _build_context(scholarships: list[Scholarship]) -> str:
    lines = []
    for s in scholarships:
        dl = s.deadline_at.isoformat() if s.deadline_at else "미정"
        amount = (s.benefit or {}).get("amount_desc", "")
        lines.append(f"- [{s.id}] {s.title} | 마감:{dl} | 혜택:{amount} | {s.source_url}")
    return "\n".join(lines) if lines else "(해당 공고 없음)"


def answer_question(db: Session, req: QARequest) -> QAResponse:
    """Q&A: 정형 후보 조회 -> grounded LLM 답변."""
    profile = req.profile or UserProfile()
    # 후보: 매칭 엔진으로 자격 통과 공고 확보(사실 기반)
    matches = match_scholarships(db, profile, category=Category.SCHOLARSHIP, limit=5)
    scholarships = [
        db.get(Scholarship, m.scholarship.id) for m in matches
    ]
    scholarships = [s for s in scholarships if s is not None]

    if not scholarships:
        return QAResponse(
            answer="조건에 맞는 모집 중 장학금을 찾지 못했습니다. 프로필을 조정하거나 나중에 다시 확인해 주세요.",
            citations=[],
            grounded=False,
        )

    context = _build_context(scholarships)
    user_prompt = f"[공고 컨텍스트]\n{context}\n\n[질문]\n{req.question}"
    if llm.has_llm():
        answer = llm.chat_complete(_QA_SYSTEM, user_prompt)
    else:
        # 폴백: 후보 공고를 근거로 규칙기반 요약 응답
        lines = [f"{i+1}. {s.title} (마감 {s.deadline_at.date() if s.deadline_at else '미정'})" for i, s in enumerate(scholarships)]
        answer = "지원 가능한 장학금 후보입니다:\n" + "\n".join(lines)

    citations = [
        QACitation(
            scholarship_id=s.id,
            title=s.title,
            deadline_at=s.deadline_at,
            source_url=s.source_url,
        )
        for s in scholarships
    ]
    return QAResponse(answer=answer, citations=citations, grounded=True)


def _gather_history(db: Session, user_id: uuid.UUID) -> list[ApplicationDocument]:
    """재사용 허용된 과거/생성 신청서의 문항 답변 수집(플라이휠 소스)."""
    stmt = (
        select(ApplicationDocument)
        .join(UserApplication, ApplicationDocument.application_id == UserApplication.id)
        .where(
            UserApplication.user_id == user_id,
            UserApplication.is_reusable.is_(True),
        )
    )
    return list(db.scalars(stmt).all())


def generate_draft(db: Session, user_id: uuid.UUID, scholarship_id: int, questions: list[str]) -> DraftResponse:
    """새 공고 문항에 대해 과거 답변 기반 초안 생성."""
    history = _gather_history(db, user_id)
    used_history = len(history) > 0

    if not history:
        # 과거 데이터 부족 -> 창작 대신 가이드 질문 유도
        answers = [
            DraftAnswer(
                question=q,
                draft_text="[보완 필요] 과거 신청 데이터가 없어 초안을 생성할 수 없습니다. "
                "관련 경험을 입력하시면 초안을 만들어 드립니다.",
                sources=[],
            )
            for q in questions
        ]
        return DraftResponse(scholarship_id=scholarship_id, answers=answers, used_history=False)

    history_blob = "\n\n".join(
        f"[문항] {d.prompt_question or '(무제)'}\n[답변] {d.content_text}" for d in history
    )

    # 공고 맥락(제목/대상/지급액)을 함께 넣어 이 공고에 맞춘 초안이 되게 한다.
    from app.models.scholarship import Scholarship

    sch = db.get(Scholarship, scholarship_id)
    if sch:
        elig = sch.eligibility or {}
        benefit = sch.benefit or {}
        scholarship_ctx = (
            f"[지원 장학금] {sch.title}\n"
            f"[주관] {sch.organization or '-'}\n"
            f"[대상] {elig.get('target_desc', '') or elig.get('scope', '')}\n"
            f"[지급액] {benefit.get('amount_desc', '') or '-'}"
        )
    else:
        scholarship_ctx = ""

    answers: list[DraftAnswer] = []
    for q in questions:
        user_prompt = (
            f"{scholarship_ctx}\n\n"
            f"[사용자 과거 답변]\n{history_blob}\n\n"
            f"[이 공고의 신청 문항]\n{q}\n\n"
            "위 과거 답변에 근거하되, 지원하는 장학금의 취지·대상에 맞춰 이 문항의 초안을 작성하라. "
            "과거 답변에 없는 사실은 지어내지 말고, 채워야 할 부분은 [보완 필요]로 표시하라."
        )
        if llm.has_llm():
            draft = llm.chat_complete(_DRAFT_SYSTEM, user_prompt, temperature=0.3)
        else:
            # 폴백: 가장 관련 있는 과거 답변을 근거로 안내형 초안 제공
            base = history[0].content_text[:400] if history else ""
            draft = (
                f"[초안 초안(폴백)] 과거 답변을 참고하세요:\n{base}\n\n"
                "[보완 필요] 이 문항에 맞게 위 내용을 다듬어 주세요."
            )
        answers.append(
            DraftAnswer(
                question=q,
                draft_text=draft,
                sources=[d.prompt_question or "(무제)" for d in history[:3]],
            )
        )

    return DraftResponse(scholarship_id=scholarship_id, answers=answers, used_history=used_history)
