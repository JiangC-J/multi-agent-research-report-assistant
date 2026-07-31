from enum import Enum
from uuid import UUID
from app.schemas.research_task import TaskStatus
from pydantic import BaseModel, Field


class WorkflowRunStatus(str, Enum):
    """
    LangGraph 工作流本次运行的状态。

    它与数据库中的 TaskStatus 有关联，但不完全相同。
    例如 awaiting_revision 表示图暂停等待返工，
    此时数据库任务通常已经回到 RESEARCHING。
    """

    CREATED = "created"
    PLANNING = "planning"
    RESEARCHING = "researching"
    ANALYZING = "analyzing"
    REVIEWING = "reviewing"
    AWAITING_REVISION = "awaiting_revision"
    WRITING = "writing"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowRunResponse(BaseModel):
    """
    一次完整 LangGraph 工作流运行后的响应。
    """

    task_id: UUID = Field(
        ...,
        description="本次执行的研究任务 ID。",
    )
    workflow_status: WorkflowRunStatus = Field(
        ...,
        description="本次 LangGraph 工作流的最终状态。",
    )
    completed_subtask_ids: list[str] = Field(
        default_factory=list,
        description="本次已经完成的研究子任务 ID 列表。",
    )
    review_outcome: str | None = Field(
        default=None,
        description=(
            "审核汇总结果，例如 PROCEED_TO_WRITING、"
            "RETURN_TO_RESEARCH 或 FAILED。"
        ),
    )
    required_actions: list[str] = Field(
        default_factory=list,
        description="Reviewer 返回的补充研究或修改要求。",
    )
    report_id: UUID | None = Field(
        default=None,
        description="成功生成报告时的报告 ID。",
    )
    execution_log: list[str] = Field(
        default_factory=list,
        description="工作流各节点的简短执行轨迹。",
    )
    error_message: str | None = Field(
        default=None,
        description="工作流失败时的错误信息。",
    )

class WorkflowTaskAcceptedResponse(BaseModel):
    """
    工作流已成功投递到 Celery 队列后的响应。

    这不是最终研究结果；
    它表示 API 已接受任务，Worker 将在后台执行。
    """

    task_id: UUID = Field(
        ...,
        description="研究任务 ID，也是后续查询业务状态的主键。",
    )
    celery_task_id: str = Field(
        ...,
        description="Celery 后台任务 ID，用于排查队列执行状态。",
    )
    workflow_run_id: UUID = Field(
        ...,
        description=(
            "SQLite 中持久化的工作流执行记录 ID。"
        ),
    )
    task_status: TaskStatus = Field(
        ...,
        description="SQLite 中的业务状态，投递成功后应为 QUEUED。",
    )
    celery_state: str = Field(
        ...,
        description="投递时的 Celery 技术状态，通常为 PENDING。",
    )
    message: str = Field(
        ...,
        description="提示客户端通过 task_id 查询业务执行进度。",
    )