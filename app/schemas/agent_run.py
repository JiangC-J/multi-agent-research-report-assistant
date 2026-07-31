from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AgentName(str, Enum):
    """
    系统中支持的 Agent 名称。
    """

    PLANNER = "PLANNER"
    RESEARCHER = "RESEARCHER"
    ANALYST = "ANALYST"
    REVIEWER = "REVIEWER"
    WRITER = "WRITER"


class AgentRunStatus(str, Enum):
    """
    单次 Agent 执行的状态。
    """

    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AgentRunStart(BaseModel):
    """
    开始一次 Agent 执行时使用的数据。
    """

    agent_name: AgentName = Field(
        ...,
        description="本次执行的 Agent。",
    )
    input_summary: str | None = Field(
        default=None,
        max_length=2000,
        description="Agent 输入的摘要，不保存完整敏感内容。",
    )


class AgentRunFinish(BaseModel):
    """
    完成一次 Agent 执行时使用的数据。
    """

    status: AgentRunStatus = Field(
        ...,
        description="执行完成后的状态，只能为 SUCCEEDED 或 FAILED。",
    )
    output_summary: str | None = Field(
        default=None,
        max_length=4000,
        description="Agent 输出结果的摘要。",
    )
    input_tokens: int = Field(
        default=0,
        ge=0,
        description="本次调用消耗的输入 Token 数。",
    )
    output_tokens: int = Field(
        default=0,
        ge=0,
        description="本次调用消耗的输出 Token 数。",
    )
    estimated_cost_usd: float = Field(
        default=0.0,
        ge=0,
        description="本次执行的预估美元成本。",
    )
    error_message: str | None = Field(
        default=None,
        max_length=2000,
        description="执行失败时的错误信息。",
    )

    @model_validator(mode="after")
    def validate_finish_data(self) -> "AgentRunFinish":
        """
        校验成功和失败场景下必须提供的信息。
        """
        if self.status == AgentRunStatus.RUNNING:
            raise ValueError("完成执行时，status 不能为 RUNNING。")

        if self.status == AgentRunStatus.SUCCEEDED:
            if not self.output_summary:
                raise ValueError("执行成功时，必须提供 output_summary。")

            if self.error_message is not None:
                raise ValueError("执行成功时，不允许提供 error_message。")

        if self.status == AgentRunStatus.FAILED and not self.error_message:
            raise ValueError("执行失败时，必须提供 error_message。")

        return self


class AgentRunResponse(BaseModel):
    """
    返回给调用方的 Agent 执行记录。
    """

    run_id: UUID = Field(
        ...,
        description="单次 Agent 执行的唯一标识。",
    )
    task_id: UUID = Field(
        ...,
        description="所属研究任务的唯一标识。",
    )
    agent_name: AgentName = Field(
        ...,
        description="执行的 Agent。",
    )
    status: AgentRunStatus = Field(
        ...,
        description="Agent 执行状态。",
    )
    input_summary: str | None = Field(
        default=None,
        description="Agent 输入摘要。",
    )
    output_summary: str | None = Field(
        default=None,
        description="Agent 输出摘要。",
    )
    started_at: datetime = Field(
        ...,
        description="执行开始时间。",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="执行完成时间。",
    )
    duration_ms: int | None = Field(
        default=None,
        description="执行耗时，单位为毫秒。",
    )
    input_tokens: int = Field(
        default=0,
        description="输入 Token 数。",
    )
    output_tokens: int = Field(
        default=0,
        description="输出 Token 数。",
    )
    estimated_cost_usd: float = Field(
        default=0.0,
        description="预估美元成本。",
    )
    error_message: str | None = Field(
        default=None,
        description="失败原因。",
    )