from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClaimReviewModel(Base):
    """
    SQLite 中的 Claim 审核记录表模型。
    """

    __tablename__ = "claim_reviews"

    review_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("research_tasks.task_id"),
        nullable=False,
        index=True,
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.claim_id"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    evidence_assessment: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    verified_evidence_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    review_comment: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    issues: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
    )
    required_actions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )