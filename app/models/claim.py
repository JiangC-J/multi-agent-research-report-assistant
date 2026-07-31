from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClaimModel(Base):
    """
    SQLite 中的结论表模型。
    """

    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("research_tasks.task_id"),
        nullable=False,
        index=True,
    )
    claim_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    claim_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    evidence_rationale: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    limitations: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    review_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    review_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class ClaimEvidenceModel(Base):
    """
    Claim 与 Evidence 的多对多关联表。
    """

    __tablename__ = "claim_evidences"

    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.claim_id"),
        primary_key=True,
    )
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("evidences.evidence_id"),
        primary_key=True,
    )