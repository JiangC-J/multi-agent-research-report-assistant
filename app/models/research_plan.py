from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResearchPlanModel(Base):
    """
    SQLite 中的研究计划表模型。
    """

    __tablename__ = "research_plans"

    plan_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("research_tasks.task_id"),
        nullable=False,
        unique=True,
        index=True,
    )
    plan_title: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    overall_strategy: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class ResearchSubTaskModel(Base):
    """
    SQLite 中的研究子任务表模型。
    """

    __tablename__ = "research_subtasks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("research_plans.plan_id"),
        nullable=False,
        index=True,
    )
    subtask_id: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    research_question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    objective: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    search_queries: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    preferred_source_types: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )