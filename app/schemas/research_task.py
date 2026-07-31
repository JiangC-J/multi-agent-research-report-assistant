from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskStatus(str, Enum):
    """
    研究任务的生命周期状态。
    """

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    RESEARCHING = "RESEARCHING"
    ANALYZING = "ANALYZING"
    REVIEWING = "REVIEWING"
    WRITING = "WRITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReportLanguage(str, Enum):
    """
    最终研究报告的输出语言。
    """

    ZH_CN = "zh-CN"
    EN_US = "en-US"


class ResearchTaskCreate(BaseModel):
    """
    用户创建研究任务时提交的数据。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "research_topic": "分析企业在客户服务场景中使用 AI Agent 的主要价值、风险和落地建议。",
                    "requirements": "重点关注中小企业，报告使用中文，控制在 1500 字以内。",
                    "report_language": "zh-CN",
                }
            ]
        }
    )

    research_topic: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="用户希望研究的主题。",
    )
    requirements: str | None = Field(
        default=None,
        max_length=1000,
        description="用户对研究范围、时间、行业或报告格式的补充要求。",
    )
    report_language: ReportLanguage = Field(
        default=ReportLanguage.ZH_CN,
        description="最终报告的输出语言。",
    )


class TaskStatusUpdate(BaseModel):
    """
    更新研究任务状态时使用的数据。
    """

    status: TaskStatus = Field(
        ...,
        description="目标任务状态。",
    )
    error_message: str | None = Field(
        default=None,
        max_length=2000,
        description="任务失败时记录的错误信息。",
    )

    @model_validator(mode="after")
    def validate_error_message(self) -> "TaskStatusUpdate":
        """
        失败任务必须提供错误信息；
        非失败任务不允许附带错误信息。
        """
        if self.status == TaskStatus.FAILED and not self.error_message:
            raise ValueError("任务状态为 FAILED 时，必须提供 error_message。")

        if self.status != TaskStatus.FAILED and self.error_message is not None:
            raise ValueError("只有任务状态为 FAILED 时，才允许提供 error_message。")

        return self


class ResearchTaskResponse(BaseModel):
    """
    创建任务或查询任务时返回给用户的数据。
    """

    task_id: UUID = Field(
        ...,
        description="研究任务的唯一标识。",
    )
    status: TaskStatus = Field(
        ...,
        description="研究任务当前状态。",
    )
    research_topic: str = Field(
        ...,
        description="用户提交的研究主题。",
    )
    requirements: str | None = Field(
        default=None,
        description="用户提交的补充要求。",
    )
    report_language: ReportLanguage = Field(
        ...,
        description="最终报告的输出语言。",
    )
    created_at: datetime = Field(
        ...,
        description="任务创建时间。",
    )
    updated_at: datetime = Field(
        ...,
        description="任务最后更新时间。",
    )
    error_message: str | None = Field(
        default=None,
        description="任务失败时的错误说明。",
    )