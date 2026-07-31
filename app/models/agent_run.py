from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentRunModel(Base):
    """
    SQLite 中的 Agent 执行记录表模型。
    """

    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("research_tasks.task_id"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    input_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    output_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    estimated_cost_usd: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )