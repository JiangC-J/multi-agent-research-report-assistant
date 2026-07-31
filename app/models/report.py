from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReportModel(Base):
    """
    SQLite 中的研究报告表模型。
    """

    __tablename__ = "reports"

    report_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("research_tasks.task_id"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    report_title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    sections: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
    )
    citations: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
    )
    markdown_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )