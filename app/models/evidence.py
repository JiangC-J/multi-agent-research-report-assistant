from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EvidenceModel(Base):
    """
    SQLite 中的证据表模型。
    """

    __tablename__ = "evidences"

    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "subtask_id",
            "source_url",
            name="uq_evidences_task_subtask_source_url",
        ),
    )

    evidence_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("research_tasks.task_id"),
        nullable=False,
        index=True,
    )
    subtask_id: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    source_title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )
    source_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    evidence_kind: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    content_excerpt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    evidence_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    relevance_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    source_quality_hint: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )