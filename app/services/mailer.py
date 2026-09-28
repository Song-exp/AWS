"""메일 발송(stdlib smtplib).

SMTP는 어디에나 있다. Gmail 앱 비밀번호, 네이버, AWS SES, Mailgun 모두
같은 인터페이스라 프로바이더 SDK를 붙이지 않아도 된다.

SMTP_HOST가 비어 있으면 **발송하지 않고 로그로 출력한다.** 로컬 개발에서
메일 서버 없이 재설정 흐름을 그대로 확인하기 위한 것이다. 운영 모드에서는
설정이 없으면 부팅이 실패하므로(core.config) 이 폴백이 운영에 새지 않는다.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.smtp_host)


def send_email(to: str, subject: str, body: str) -> None:
    """메일 한 통 발송. 실패는 예외로 올린다(호출부가 정책을 정한다)."""
    if not is_configured():
        # 개발 폴백: 실제로 보내지 않고 내용을 남긴다.
        logger.warning(
            "SMTP 미설정 — 메일을 보내지 않고 출력합니다.\n"
            "  To: %s\n  Subject: %s\n%s", to, subject, body
        )
        return

    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if settings.smtp_use_ssl:
        # 465 포트는 처음부터 TLS로 연결한다(SMTPS).
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    try:
        if not settings.smtp_use_ssl and settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    finally:
        server.quit()


def send_password_reset(to: str, reset_url: str, ttl_minutes: int) -> None:
    """비밀번호 재설정 링크 안내.

    본문에 계정 정보를 담지 않는다. 메일은 평문으로 남고 전달될 수 있다.
    """
    send_email(
        to=to,
        subject="[대학생 혜택 통합 서비스] 비밀번호 재설정",
        body=(
            "비밀번호 재설정을 요청하셨습니다.\n\n"
            f"아래 링크에서 새 비밀번호를 설정해 주세요. {ttl_minutes}분 뒤 만료됩니다.\n\n"
            f"{reset_url}\n\n"
            "본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다.\n"
            "링크를 쓰지 않으면 비밀번호는 그대로 유지됩니다.\n"
        ),
    )


def send_deadline_reminder(to: str, items: list[dict]) -> None:
    """마감 임박 공고 알림.

    돈을 못 아끼는 1위 원인은 '비싸게 샀다'가 아니라 '기간이 지나서 못
    받았다'다. 지도도 챗봇도 사용자가 먼저 열어야 동작하므로, 먼저 찾아가는
    경로가 하나는 있어야 한다.

    한 통에 모아 보낸다. 공고마다 따로 보내면 스팸으로 분류된다.
    """
    lines = []
    for it in items:
        left = it.get("days_left")
        when = f"D-{left}" if left is not None else "마감 임박"
        lines.append(f"  [{when}] {it['title']}\n         {it['url']}")

    send_email(
        to=to,
        subject=f"[대학생 혜택 통합 서비스] 마감 임박 공고 {len(items)}건",
        body=(
            "신청 기간이 얼마 남지 않은 공고가 있습니다.\n\n"
            + "\n".join(lines)
            + "\n\n알림이 필요 없으면 마이페이지에서 끌 수 있습니다.\n"
        ),
    )
