"""기본 게시판 시드.

게시판이 하나도 없으면 커뮤니티 탭이 빈 화면이라 서비스가 시작되지 않는다.
slug 기준 upsert라 여러 번 실행해도 중복되지 않는다.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.community import Board, BoardCategory

# (slug, 이름, 설명, 카테고리, 익명허용, 익명강제, 정렬)
BOARDS: list[tuple[str, str, str, BoardCategory, bool, bool, int]] = [
    ("free", "자유게시판", "무엇이든 자유롭게",
     BoardCategory.GENERAL, True, False, 10),
    ("secret", "비밀게시판", "익명으로만 쓸 수 있어요",
     BoardCategory.GENERAL, True, True, 20),
    ("freshman", "새내기게시판", "1학년끼리 묻고 답하기",
     BoardCategory.GENERAL, True, False, 30),
    ("graduate", "졸업생게시판", "졸업생 라운지",
     BoardCategory.GENERAL, True, False, 40),
    # 기획서의 커뮤니티 목적(절약 꿀팁·공동구매)에 해당하는 게시판
    ("saving-tips", "절약 꿀팁", "학교 앞 최저가와 할인 정보 공유",
     BoardCategory.GENERAL, True, False, 50),
    ("groupbuy", "공동구매", "생필품·식자재 같이 사요",
     BoardCategory.GROUP, False, False, 60),
    ("career", "진로·취업", "인턴, 자격증, 대학원",
     BoardCategory.CAREER, True, False, 70),
    ("promo", "홍보게시판", "행사·모집 홍보(실명)",
     BoardCategory.PROMO, False, False, 80),
    ("club", "동아리·학회", "단체 모집과 활동",
     BoardCategory.GROUP, True, False, 90),
]


def seed_boards() -> dict:
    db = SessionLocal()
    created = updated = 0
    try:
        for slug, name, desc, category, allows, forces, order in BOARDS:
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
                updated += 1
        db.commit()
    finally:
        db.close()
    return {"created": created, "updated": updated, "total": len(BOARDS)}


if __name__ == "__main__":
    import json

    print(json.dumps(seed_boards(), ensure_ascii=False, indent=2))
