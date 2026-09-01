"""SQLAlchemy 모델 집합."""
from app.models.scholarship import Scholarship, ScholarshipEmbedding
from app.models.application import (
    ApplicationDocument,
    DocumentEmbedding,
    UserApplication,
)
from app.models.crawl_run import CrawlRun, CrawlRunStatus
from app.models.store import PayMethod, Store, StoreCategory, StoreOffer
from app.models.card import (
    BenefitType,
    Card,
    CardBenefit,
    Confidence,
    PeriodType,
)
from app.models.user import User
from app.models.auth_session import AuthSession
from app.models.password_reset import PasswordResetToken
from app.models.community import (
    Board,
    BoardCategory,
    BoardRead,
    Comment,
    CommentLike,
    Post,
    PostLike,
    Report,
    Scrap,
)
from app.models.local_benefit import LocalBenefitMerchant
from app.models.saving import SavingKind, SavingRecord

__all__ = [
    # 장학금 챗봇
    "Scholarship",
    "ScholarshipEmbedding",
    "UserApplication",
    "ApplicationDocument",
    "DocumentEmbedding",
    "CrawlRun",
    "CrawlRunStatus",
    # 페이픽 지도
    "Store",
    "StoreOffer",
    "StoreCategory",
    "PayMethod",
    "Card",
    "CardBenefit",
    "BenefitType",
    "Confidence",
    "PeriodType",
    "LocalBenefitMerchant",
    "SavingRecord",
    "SavingKind",
    # 공통
    "User",
    "AuthSession",
    "PasswordResetToken",
    "Board",
    "BoardCategory",
    "BoardRead",
    "Comment",
    "CommentLike",
    "Post",
    "PostLike",
    "Report",
    "Scrap",
]
