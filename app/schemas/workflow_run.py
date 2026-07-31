from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowRunStatus(str, Enum):
    """
    一次完整后台工作流执行的状态。
    """

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class WorkflowRunResponse(BaseModel):
    """
    持久化后的工作流执行记录。

    一条记录对应一次 Celery 后台执行尝试。
    """

    run_id: UUID = Field(
        ...,
        description="工作流执行记录 ID。",
    )
    task_id: UUID = Field(
        ...,
        description="所属研究任务 ID。",
    )
    celery_task_id: str = Field(
        ...,
        min_length=1,
        description="Celery 后台任务 ID。",
    )
    status: WorkflowRunStatus = Field(
        ...,
        description="当前工作流执行状态。",
    )
    queued_at: datetime = Field(
        ...,
        description="任务进入 Celery 队列的时间。",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Worker 实际开始执行的时间。",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="工作流执行结束的时间。",
    )
    duration_ms: int | None = Field(
        default=None,
        ge=0,
        description="Worker 实际执行耗时，单位为毫秒。",
    )
    error_message: str | None = Field(
        default=None,
        description="后台执行失败时的错误摘要。",
    )