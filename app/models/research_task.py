from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResearchTaskModel(Base):
    """
    SQLite 中的研究任务表模型。
    """

    __tablename__ = "research_tasks"

    task_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    research_topic: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    requirements: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    report_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )