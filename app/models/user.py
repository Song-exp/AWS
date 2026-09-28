"""사용자 모델.

두 서비스(지도·챗봇)를 하나로 합치면서 공통 프로필이 필요해졌다.
- 챗봇: 소득분위·학점·지역 등 장학금 매칭 자격
- 지도: 선호 결제수단(카카오/토스/네이버페이)
기존 코드가 user_id(UUID)만 들고 있던 것을 실제 테이블로 승격한다.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import GUIDType, JSONType, StrListType


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUIDType, primary_key=True, default=uuid.uuid4)

    nickname: Mapped[str | None] = mapped_column(String(50))
    # 이메일은 소문자로 정규화해 저장한다(대소문자만 다른 중복 가입 방지).
    email: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)

    # scrypt 해시. 'scrypt$n$r$p$salt$hash' 형식(app.core.security 참고).
    # 익명 사용자는 계정이 없으므로 nullable 이다.
    password_hash: Mapped[str | None] = mapped_column(String(255))

    # 인증 메일의 링크를 눌렀거나 비밀번호 재설정을 마친 시각. NULL이면 이 주소가
    # 본인 것인지 모른다. 그런 주소로는 알림 메일을 보내지 않는다.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 마감 알림 메일 수신 동의. 기본은 꺼짐이고 가입·마이페이지에서 직접 켠다.
    reminder_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    # 개인정보 수집·이용에 동의한 시각. 동의 없이는 가입할 수 없다.
    privacy_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- 장학금 매칭용 프로필 ---
    income_bracket: Mapped[int | None] = mapped_column(Integer)   # 소득분위 0~10
    gpa: Mapped[float | None] = mapped_column(Float)
    grade_level: Mapped[str | None] = mapped_column(String(10))   # '1'~'4'
    region: Mapped[str | None] = mapped_column(String(50))
    major: Mapped[str | None] = mapped_column(String(100))
    interests: Mapped[list[str]] = mapped_column(StrListType, default=list)

    # --- 지도(페이픽) 개인화 ---
    # 온보딩에서 모으던 값들. 지금까지 localStorage 에만 있어서 기기를 바꾸면
    # 사라졌고 서버가 개인화에 쓰지도 못했다. 계정이 생겼으므로 여기로 올린다.
    preferred_pay_methods: Mapped[list[str]] = mapped_column(StrListType, default=list)
    gender: Mapped[str | None] = mapped_column(String(10))          # 'male' | 'female'
    telecom: Mapped[str | None] = mapped_column(String(30))
    # 보유 카드 ID 목록. 정수 배열이라 StrListType 대신 JSON 을 쓴다.
    card_ids: Mapped[list] = mapped_column(JSONType, default=list)
    student_credentials: Mapped[list[str]] = mapped_column(StrListType, default=list)
    benefit_programs: Mapped[list[str]] = mapped_column(StrListType, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
