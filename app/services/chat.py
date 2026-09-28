"""챗봇 대화 오케스트레이션.

목적: **사용자 조건에 맞는 장학금을 찾아주는 것**.

설계:
  - 확정적 동작(후보 번호 선택, '저장')은 규칙으로 처리해 오작동을 막는다.
  - 그 외 자유 발화는 DeepSeek LLM이 담당한다. 조건이 덜 모였으면 하나씩
    물어보고, 모이면 DB에서 후보를 뽑아 근거와 함께 제시한다.
  - 어떤 상태에서든 새로운 조건(예: '5분위야', '학점 3.8')을 말하면 즉시
    프로필을 갱신하고 재매칭한다(막다른 길 없음).
  - LLM은 DB에서 찾은 공고 컨텍스트 밖의 장학금을 만들어내지 않는다.

대화 흐름(느슨한 상태):
  조건 수집 → 후보 제시 → 선택 → (과거기록 O: 초안 / X: 자기소개 수집 → 초안)
  → 아카이빙
"""
from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.application import (
    ApplicationDocument,
    ApplicationResult,
    ApplicationSource,
    DocType,
    UserApplication,
)
from app.models.scholarship import Category, PostingStatus, Scholarship
from app.schemas.schemas import UserProfile
from app.services import llm, rag
from app.services.matching import match_scholarships

logger = logging.getLogger(__name__)


class ChatState(str, Enum):
    COLLECT = "collect"            # 조건 수집 중
    SELECT = "select"              # 후보 중 선택 대기
    COLLECT_INTRO = "collect_intro"  # 자기소개 수집(과거 기록 없을 때)
    ARCHIVE = "archive"            # 초안 확인 후 저장 대기
    DONE = "done"


# ---------------- 시스템 프롬프트 ----------------
_SYSTEM = """너는 대학생 장학금 매칭 상담사다. 목표는 사용자의 조건에 맞는 장학금을 찾아주는 것이다.

[역할]
- 사용자에게 필요한 조건을 자연스럽게 물어 모은다: 소득분위(0~10), 학점(4.5 기준), 학년, 거주 지역, 전공/계열, 관심 분야.
- 조건이 부족하면 한 번에 하나씩만 물어본다. 이미 알고 있는 정보는 다시 묻지 않는다.
- 조건이 모이면 제공된 '검색된 공고' 목록을 근거로 추천한다.

[매우 중요한 제약]
- '검색된 공고' 목록에 없는 장학금 이름·마감일·금액을 절대 만들어내지 마라.
- 목록이 비어 있으면 추천하는 척하지 말고, 아직 공고 데이터가 없다고 솔직히 말한 뒤 다른 도움(과거 신청서 업로드, 조건 보완)을 제안하라.
- 마감일·지원금액 같은 수치는 제공된 목록에 있는 값만 사용하라.

[말투]
- 한국어, 친근하고 간결하게. 2~4문장 이내.
- 매 답변 끝에는 사용자가 다음에 할 수 있는 행동을 한 가지 제시하라.
"""


@dataclass
class ChatSession:
    session_id: str
    user_id: uuid.UUID | None = None
    state: ChatState = ChatState.COLLECT
    profile: UserProfile = field(default_factory=UserProfile)
    candidates: list[int] = field(default_factory=list)
    selected_id: int | None = None
    intro_answers: list[str] = field(default_factory=list)
    draft: dict | None = None
    history: list[tuple[str, str]] = field(default_factory=list)  # (role, text)
    uploaded_docs: int = 0
    last_seen: float = field(default_factory=time.monotonic)


_SESSIONS: dict[str, ChatSession] = {}
_SESSIONS_LOCK = threading.Lock()
# ponytail: 프로세스 메모리 세션이라 만료와 상한을 직접 둔다. 없으면 방문자 수만큼
# 끝없이 쌓여 메모리가 작은 서버에서 프로세스가 죽는다. 인스턴스를 늘리게 되면
# Redis(TTL 내장)로 옮기고 이 코드는 지운다.
SESSION_IDLE_SEC = 6 * 3600
MAX_SESSIONS = 2000


def _evict_sessions(now: float) -> None:
    """오래 안 쓴 세션을 버린다. 상한을 넘으면 가장 오래된 것부터 버린다."""
    for sid, sess in list(_SESSIONS.items()):
        if now - sess.last_seen > SESSION_IDLE_SEC:
            del _SESSIONS[sid]
    overflow = len(_SESSIONS) - MAX_SESSIONS + 1
    if overflow > 0:
        oldest = sorted(_SESSIONS.items(), key=lambda kv: kv[1].last_seen)[:overflow]
        for sid, _ in oldest:
            del _SESSIONS[sid]


def get_or_create_session(session_id: str | None, user_id: uuid.UUID | None) -> ChatSession:
    now = time.monotonic()
    with _SESSIONS_LOCK:
        sess = _SESSIONS.get(session_id) if session_id else None
        if sess is not None and now - sess.last_seen <= SESSION_IDLE_SEC:
            sess.last_seen = now
            return sess
        _evict_sessions(now)
        sid = session_id or uuid.uuid4().hex
        sess = ChatSession(session_id=sid, user_id=user_id, last_seen=now)
        _SESSIONS[sid] = sess
        return sess


# ---------------- 조건 파싱 ----------------
_BRACKET_RE = re.compile(r"(10|[0-9])\s*분위")
# '3.8점', '3.8 학점' (숫자 먼저) / '학점은 3.8', '학점 3.8' (라벨 먼저) 모두 지원
_GPA_AFTER_RE = re.compile(r"(\d(?:\.\d+)?)\s*(?:점|학점)")
_GPA_BEFORE_RE = re.compile(r"학점\s*(?:은|이|:)?\s*(\d(?:\.\d+)?)")
_GRADE_RE = re.compile(r"([1-4])\s*학년")
_REGIONS = [
    "서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]
_MAJOR_HINTS = {
    "공학": "공학", "이공": "이공계", "인문": "인문", "사회": "사회과학",
    "예술": "예술", "체육": "체육", "의학": "의학", "간호": "간호",
    "경영": "경영", "컴퓨터": "컴퓨터", "소프트웨어": "컴퓨터",
}


def _parse_profile(text: str, profile: UserProfile) -> list[str]:
    """자유 발화에서 조건을 추출해 프로필을 갱신. 갱신된 필드명 목록 반환."""
    updated: list[str] = []

    m = _BRACKET_RE.search(text)
    if m:
        v = int(m.group(1))
        if profile.income_bracket != v:
            profile.income_bracket = v
            updated.append("소득분위")

    g = _GPA_BEFORE_RE.search(text) or _GPA_AFTER_RE.search(text)
    if g:
        try:
            v = float(g.group(1))
            if 0 <= v <= 4.5 and profile.gpa != v:
                profile.gpa = v
                updated.append("학점")
        except ValueError:
            pass

    gr = _GRADE_RE.search(text)
    if gr and profile.grade_level != gr.group(1):
        profile.grade_level = gr.group(1)
        updated.append("학년")

    for r in _REGIONS:
        if r in text and profile.region != r:
            profile.region = r
            updated.append("지역")
            break

    for kw, major in _MAJOR_HINTS.items():
        if kw in text and profile.major != major:
            profile.major = major
            updated.append("전공")
            break

    return updated


def _missing_fields(profile: UserProfile) -> list[str]:
    missing = []
    if profile.income_bracket is None:
        missing.append("소득분위")
    if profile.gpa is None:
        missing.append("학점")
    if not profile.region:
        missing.append("지역")
    return missing


def _profile_summary(profile: UserProfile) -> str:
    parts = []
    if profile.income_bracket is not None:
        parts.append(f"소득 {profile.income_bracket}분위")
    if profile.gpa is not None:
        parts.append(f"학점 {profile.gpa}")
    if profile.grade_level:
        parts.append(f"{profile.grade_level}학년")
    if profile.region:
        parts.append(profile.region)
    if profile.major:
        parts.append(profile.major)
    return ", ".join(parts) if parts else "(아직 정보 없음)"


def _select_index(text: str, n: int) -> int | None:
    m = re.search(r"(\d+)\s*번", text) or re.fullmatch(r"\s*(\d+)\s*", text)
    if not m:
        return None
    idx = int(m.group(1)) - 1
    return idx if 0 <= idx < n else None


@dataclass
class BotReply:
    session_id: str
    state: str
    message: str
    candidates: list[dict] = field(default_factory=list)
    draft: dict | None = None
    profile: dict = field(default_factory=dict)


def _history_count(db: Session, user_id: uuid.UUID | None) -> int:
    if not user_id:
        return 0
    return db.scalar(
        select(func.count())
        .select_from(UserApplication)
        .where(UserApplication.user_id == user_id, UserApplication.is_reusable.is_(True))
    ) or 0


def _scholarship_total(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Scholarship)
        .where(
            Scholarship.category == Category.SCHOLARSHIP,
            Scholarship.status.in_([PostingStatus.OPEN, PostingStatus.CLOSING_SOON]),
        )
    ) or 0


def _search_candidates(db: Session, sess: ChatSession) -> list[dict]:
    """현재 프로필로 DB에서 후보를 찾아 LLM 컨텍스트/응답용 구조로 반환."""
    results = match_scholarships(db, sess.profile, category=Category.SCHOLARSHIP, limit=5)
    sess.candidates = [r.scholarship.id for r in results]
    return [
        {
            "index": i + 1,
            "id": r.scholarship.id,
            "title": r.scholarship.title,
            "deadline": r.scholarship.deadline_at.date().isoformat()
            if r.scholarship.deadline_at
            else "미정",
            "reasons": r.reasons,
        }
        for i, r in enumerate(results)
    ]


def _llm_reply(sess: ChatSession, user_text: str, cands: list[dict], total: int) -> str:
    """LLM으로 대화 응답 생성. 키가 없으면 규칙기반 폴백."""
    ctx_lines = [
        f"[사용자 조건] {_profile_summary(sess.profile)}",
        f"[부족한 조건] {', '.join(_missing_fields(sess.profile)) or '없음'}",
        f"[DB의 모집중 장학금 총건수] {total}",
        f"[업로드한 과거 신청서 수] {sess.uploaded_docs}",
    ]
    if cands:
        ctx_lines.append("[검색된 공고]")
        for c in cands:
            ctx_lines.append(f"  {c['index']}. {c['title']} (마감 {c['deadline']})")
    else:
        ctx_lines.append("[검색된 공고] 없음")

    if not llm.has_llm():
        return _fallback_reply(sess, cands, total)

    recent = sess.history[-6:]
    convo = "\n".join(f"{'사용자' if r == 'user' else '상담사'}: {t}" for r, t in recent)
    prompt = (
        "\n".join(ctx_lines)
        + (f"\n\n[최근 대화]\n{convo}" if convo else "")
        + f"\n\n[사용자 발화]\n{user_text}\n\n위 정보를 바탕으로 상담사로서 답하라."
    )
    try:
        return llm.chat_complete(_SYSTEM, prompt, temperature=0.4).strip()
    except Exception:  # noqa: BLE001 - LLM 실패 시 대화가 끊기면 안 된다
        logger.exception("chat LLM failed")
        return _fallback_reply(sess, cands, total)


def _fallback_reply(sess: ChatSession, cands: list[dict], total: int) -> str:
    """LLM 없이도 대화가 이어지도록 하는 규칙기반 응답."""
    if cands:
        lines = "\n".join(f"{c['index']}. {c['title']} (마감 {c['deadline']})" for c in cands)
        return f"조건에 맞는 장학금이에요. 번호로 선택해 주세요:\n{lines}"
    missing = _missing_fields(sess.profile)
    if total == 0:
        return (
            f"조건은 {_profile_summary(sess.profile)}로 확인했어요.\n"
            "아직 장학금 공고 데이터가 수집되지 않아 추천은 어려워요. "
            "과거 신청서를 첨부해두시면 나중에 초안을 더 정확히 만들어 드릴 수 있어요."
        )
    if missing:
        return f"{missing[0]}을(를) 알려주시면 더 정확히 찾아드릴게요."
    return "조건에 맞는 공고를 찾지 못했어요. 지역이나 전공을 바꿔서 다시 찾아볼까요?"


def _do_draft(db: Session, sess: ChatSession) -> BotReply:
    # 선택한 공고의 실제 신청 문항을 우선 사용(첨부 파싱으로 추출된 양식).
    # 없으면 일반적인 기본 문항으로 대체한다.
    questions = ["지원 동기를 서술하세요.", "본인의 강점과 활동 경험을 서술하세요."]
    scholarship = db.get(Scholarship, sess.selected_id) if sess.selected_id else None
    if scholarship and scholarship.eligibility:
        aq = scholarship.eligibility.get("application_questions")
        if isinstance(aq, list) and aq:
            questions = aq

    if sess.user_id and _history_count(db, sess.user_id) > 0:
        resp = rag.generate_draft(db, sess.user_id, sess.selected_id, questions)
        sess.draft = resp.model_dump()
    else:
        intro = "\n".join(sess.intro_answers)
        sess.draft = {
            "scholarship_id": sess.selected_id,
            "answers": [
                {
                    "question": q,
                    "draft_text": f"[초안] {intro[:200]}\n\n[보완 필요] 문항에 맞게 다듬어 주세요.",
                    "sources": [],
                }
                for q in questions
            ],
            "used_history": False,
        }
    sess.state = ChatState.ARCHIVE
    return BotReply(
        session_id=sess.session_id,
        state=sess.state.value,
        message="초안을 만들었어요. 확인하시고 '저장'이라고 하면 이 서비스에 보관해둘게요.",
        draft=sess.draft,
        profile=sess.profile.model_dump(),
    )


def _do_archive(db: Session, sess: ChatSession) -> BotReply:
    scholarship = db.get(Scholarship, sess.selected_id) if sess.selected_id else None
    app_row = UserApplication(
        user_id=sess.user_id or uuid.uuid4(),
        scholarship_name=scholarship.title if scholarship else "(제목미상)",
        organization=scholarship.organization if scholarship else None,
        scholarship_id=sess.selected_id,
        source=ApplicationSource.GENERATED,
        result=ApplicationResult.DRAFT,
        is_reusable=True,
    )
    for ans in (sess.draft or {}).get("answers", []):
        app_row.documents.append(
            ApplicationDocument(
                doc_type=DocType.SELF_INTRO,
                prompt_question=ans.get("question"),
                content_text=ans.get("draft_text", ""),
                char_count=len(ans.get("draft_text", "")),
            )
        )
    db.add(app_row)
    db.commit()
    sess.state = ChatState.COLLECT  # 저장 후에도 대화를 계속할 수 있게 되돌린다
    return BotReply(
        session_id=sess.session_id,
        state=sess.state.value,
        message="지원서를 저장했어요. 쓸수록 다음 초안이 정확해져요. 다른 조건으로 더 찾아볼까요?",
        profile=sess.profile.model_dump(),
    )


def note_upload(db: Session, session_id: str | None, user_id: uuid.UUID | None,
                filename: str, text_len: int) -> BotReply:
    """채팅 중 파일 업로드가 끝났을 때의 봇 응답."""
    sess = get_or_create_session(session_id, user_id)
    if user_id and sess.user_id is None:
        sess.user_id = user_id
    sess.uploaded_docs += 1
    sess.history.append(("user", f"(파일 첨부: {filename})"))

    msg = (
        f"'{filename}' 잘 받았어요. 본문 {text_len:,}자를 읽어서 보관했어요.\n"
        "이 내용을 근거로 초안을 만들 수 있어요."
    )
    sess.history.append(("bot", msg))
    return BotReply(
        session_id=sess.session_id,
        state=sess.state.value,
        message=msg,
        profile=sess.profile.model_dump(),
    )


# 계정에 저장되는 매칭 조건. 대화에서 알아낸 값을 여기에 싣고 되싣는다.
_PERSISTED_PROFILE_FIELDS = ("income_bracket", "gpa", "grade_level", "region", "major")


def _load_profile_from_account(db: Session, sess: ChatSession) -> None:
    """계정에 저장된 조건을 대화 프로필의 출발점으로 삼는다.

    대화 세션은 프로세스 메모리에 있어 서버가 재시작하면 사라진다. 계정에
    붙여 두면 사용자가 소득분위·학점을 매번 다시 말하지 않아도 된다.
    """
    if sess.user_id is None:
        return
    from app.models.user import User

    user = db.get(User, sess.user_id)
    if user is None:
        return
    for field in _PERSISTED_PROFILE_FIELDS:
        if getattr(sess.profile, field, None) is None:
            value = getattr(user, field, None)
            if value is not None:
                setattr(sess.profile, field, value)


def _save_profile_to_account(db: Session, sess: ChatSession) -> None:
    """대화에서 알아낸 조건을 계정에 남긴다(비로그인이면 아무것도 안 한다)."""
    if sess.user_id is None:
        return
    from app.models.user import User

    user = db.get(User, sess.user_id)
    if user is None:
        return
    changed = False
    for field in _PERSISTED_PROFILE_FIELDS:
        value = getattr(sess.profile, field, None)
        if value is not None and getattr(user, field, None) != value:
            setattr(user, field, value)
            changed = True
    if changed:
        db.commit()


def handle_message(
    db: Session, session_id: str | None, user_id: uuid.UUID | None, text: str
) -> BotReply:
    """대화 한 턴 처리."""
    sess = get_or_create_session(session_id, user_id)
    if user_id and sess.user_id is None:
        sess.user_id = user_id
    _load_profile_from_account(db, sess)
    text = (text or "").strip()
    sess.history.append(("user", text))

    # 1) 확정적 동작: 후보 선택
    if sess.state == ChatState.SELECT and sess.candidates:
        idx = _select_index(text, len(sess.candidates))
        if idx is not None:
            sess.selected_id = sess.candidates[idx]
            if sess.user_id and _history_count(db, sess.user_id) > 0:
                return _do_draft(db, sess)
            sess.state = ChatState.COLLECT_INTRO
            msg = (
                "과거 신청 기록이 없네요. 간단한 자기소개를 부탁해요. "
                "본인의 활동이나 강점을 한두 문장으로 알려주시거나, 예전 신청서 PDF를 첨부해 주세요."
            )
            sess.history.append(("bot", msg))
            return BotReply(
                session_id=sess.session_id,
                state=sess.state.value,
                message=msg,
                profile=sess.profile.model_dump(),
            )

    # 2) 확정적 동작: 저장
    if sess.state == ChatState.ARCHIVE and any(
        k in text for k in ("저장", "아카이빙", "보관", "save")
    ):
        return _do_archive(db, sess)

    # 3) 자기소개 수집 중이면 답변을 모으고 초안 생성
    if sess.state == ChatState.COLLECT_INTRO and text:
        sess.intro_answers.append(text)
        return _do_draft(db, sess)

    # 4) 그 외: 조건 갱신 + 재검색 + LLM 대화 (어떤 상태에서도 막히지 않음)
    _parse_profile(text, sess.profile)
    # 알아낸 조건은 계정에 남긴다. 다음 대화에서 다시 묻지 않기 위해서다.
    _save_profile_to_account(db, sess)
    total = _scholarship_total(db)
    cands = _search_candidates(db, sess) if sess.profile.income_bracket is not None else []
    sess.state = ChatState.SELECT if cands else ChatState.COLLECT

    msg = _llm_reply(sess, text, cands, total)
    sess.history.append(("bot", msg))
    return BotReply(
        session_id=sess.session_id,
        state=sess.state.value,
        message=msg,
        candidates=cands,
        draft=sess.draft if sess.state == ChatState.ARCHIVE else None,
        profile=sess.profile.model_dump(),
    )
