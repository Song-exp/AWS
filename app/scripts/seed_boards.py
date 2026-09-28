"""기본 게시판 시드.

게시판이 하나도 없으면 커뮤니티 탭이 빈 화면이라 서비스가 시작되지 않는다.
slug 기준 upsert라 여러 번 실행해도 중복되지 않는다.

**활성 게시판은 둘뿐이다 — 절약 꿀팁, 공동구매.**
자유·비밀·진로 같은 범용 게시판은 콘텐츠 볼륨으로 경쟁하는 판이고 이미
이긴 서비스(에브리타임)가 있다. 우리 데이터가 붙는 글만 남긴다. 지운 게
아니라 is_active 를 내린 것이라, 필요해지면 값 하나로 되살아난다.

익명 정책도 여기서 갈린다. 기준은 주제가 아니라 **틀렸을 때 누가 손해를
보느냐**다. 꿀팁이 틀리면 따라한 사람이 돈을 잃으므로 책임질 이름이 붙어야
한다(별명 + 등급). 익명이 필요한 글은 손해가 글쓴이에게만 남는 종류인데,
그 게시판들은 지금 비활성이다.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.community import Board, BoardCategory

# (slug, 이름, 설명, 카테고리, 익명허용, 익명강제, 정렬, 활성)
BOARDS: list[tuple[str, str, str, BoardCategory, bool, bool, int, bool]] = [
    # --- 활성: 돈 아끼는 데 직접 붙는 두 개 ---
    ("saving-tips", "절약 꿀팁", "학교 앞 최저가와 할인 정보 공유",
     BoardCategory.GENERAL, False, False, 10, True),
    ("groupbuy", "공동구매", "생필품·식자재 같이 사요",
     BoardCategory.GROUP, False, False, 20, True),

    # --- 비활성: 에브리타임과 겹치거나, 아직 쓸 사람이 없는 것 ---
    ("free", "자유게시판", "무엇이든 자유롭게",
     BoardCategory.GENERAL, True, False, 110, False),
    ("secret", "비밀게시판", "익명으로만 쓸 수 있어요",
     BoardCategory.GENERAL, True, True, 120, False),
    ("freshman", "새내기게시판", "1학년끼리 묻고 답하기",
     BoardCategory.GENERAL, True, False, 130, False),
    ("graduate", "졸업생게시판", "졸업생 라운지",
     BoardCategory.GENERAL, True, False, 140, False),
    ("career", "진로·취업", "인턴, 자격증, 대학원",
     BoardCategory.CAREER, True, False, 150, False),
    # 홍보는 광고주가 붙으면 켠다. 지금 켜두면 빈 게시판이다.
    ("promo", "홍보게시판", "행사·모집 홍보(실명)",
     BoardCategory.PROMO, False, False, 160, False),
    ("club", "동아리·학회", "단체 모집과 활동",
     BoardCategory.GROUP, False, False, 170, False),
]


def seed_boards() -> dict:
    db = SessionLocal()
    created = updated = 0
    try:
        for slug, name, desc, category, allows, forces, order, active in BOARDS:
            row = db.scalar(select(Board).where(Board.slug == slug))
            if row is None:
                db.add(
                    Board(
                        slug=slug,
                        name=name,
                        description=desc,
                        category=category,
                        allows_anonymous=allows,
                        forces_anonymous=forces,
                        sort_order=order,
                        is_active=active,
                    )
                )
                created += 1
            else:
                row.name = name
                row.description = desc
                row.category = category
                row.allows_anonymous = allows
                row.forces_anonymous = forces
                row.sort_order = order
                row.is_active = active
                updated += 1
        db.commit()
    finally:
        db.close()
    return {
        "created": created,
        "updated": updated,
        "total": len(BOARDS),
        "active": sum(1 for b in BOARDS if b[7]),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(seed_boards(), ensure_ascii=False, indent=2))
