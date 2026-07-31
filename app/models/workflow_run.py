from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkflowRunModel(Base):
    """
    SQLite 中的一次完整工作流执行记录。

    它记录 Celery Worker 对研究任务的每一次执行尝试。
    """

    __tablename__ = "workflow_runs"

    run_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("research_tasks.task_id"),
        nullable=False,
        index=True,
    )
    celery_task_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )