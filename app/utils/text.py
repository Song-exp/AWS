"""DB에 넣기 전 문자열 정리.

PostgreSQL 의 text·jsonb 컬럼은 NUL 바이트(0x00)를 담을 수 없다. 넣으려 하면
`psycopg.DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes` 로
트랜잭션 전체가 실패한다. SQLite 는 그냥 받아주므로 로컬에서는 드러나지 않고
운영 배포에서 처음 터진다.

NUL 은 사람이 쓴 글에는 없다. PDF 텍스트 추출, 한글 문서 파싱, 외부 API 응답
같은 기계 출력에서 섞여 들어온다. 그러니 지워도 잃는 내용이 없다.
"""
from __future__ import annotations

from typing import Any


def strip_nul(value: Any) -> Any:
    """문자열에서 NUL 을 제거한다. dict·list 는 안쪽까지 훑는다.

    JSON 컬럼(자격·지급액·제출서류)도 같은 제약을 받기 때문에 중첩 구조를
    따라 들어간다. 문자열이 아닌 값은 그대로 돌려준다.
    """
    if isinstance(value, str):
        return value.replace("\x00", "") if "\x00" in value else value
    if isinstance(value, dict):
        return {k: strip_nul(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(strip_nul(v) for v in value)
    return value
