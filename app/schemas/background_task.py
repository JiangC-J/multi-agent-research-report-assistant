from typing import Any

from pydantic import BaseModel, Field


class BackgroundTaskStatusResponse(BaseModel):
    """
    Celery 后台任务的技术执行状态。

    它与 ResearchTask.status 不同：
    - ResearchTask.status 表示研究业务执行到哪个阶段；
    - celery_state 表示 Worker 是否收到、执行或失败。
    """

    celery_task_id: str = Field(
        ...,
        description="Celery 任务 ID。",
    )
    celery_state: str = Field(
        ...,
        description=(
            "Celery 技术状态，例如 PENDING、STARTED、"
            "SUCCESS、FAILURE、RETRY。"
        ),
    )
    is_ready: bool = Field(
        ...,
        description="任务是否已经进入终态。",
    )
    is_successful: bool | None = Field(
        default=None,
        description=(
            "任务结束后是否成功；"
            "未结束时为 null。"
        ),
    )
    result: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Celery 成功任务返回的摘要结果。"
            "最终报告仍应通过 report 接口获取。"
        ),
    )
    error_message: str | None = Field(
        default=None,
        description="Celery 失败任务的错误摘要。",
    )