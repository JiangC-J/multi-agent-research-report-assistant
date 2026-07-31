from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceType(str, Enum):
    """
    Researcher 优先检索的资料来源类型。
    """

    OFFICIAL_DOCUMENT = "OFFICIAL_DOCUMENT"
    INDUSTRY_REPORT = "INDUSTRY_REPORT"
    ACADEMIC_PAPER = "ACADEMIC_PAPER"
    NEWS = "NEWS"
    CASE_STUDY = "CASE_STUDY"


class ResearchSubTask(BaseModel):
    """
    一个可由 Researcher 独立执行的研究子任务。
    """

    subtask_id: str = Field(
        ...,
        pattern=r"^subtask_[1-5]$",
        description="子任务标识，例如 subtask_1。",
    )
    title: str = Field(
        ...,
        min_length=5,
        max_length=120,
        description="子任务标题。",
    )
    research_question: str = Field(
        ...,
        min_length=10,
        max_length=300,
        description="该子任务需要回答的具体研究问题。",
    )
    objective: str = Field(
        ...,
        min_length=10,
        max_length=300,
        description="该子任务的研究目标。",
    )
    search_queries: list[str] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="Researcher 后续使用的检索查询。",
    )
    preferred_source_types: list[SourceType] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="该子任务优先使用的来源类型。",
    )
    priority: int = Field(
        ...,
        ge=1,
        le=5,
        description="子任务优先级，1 表示最高优先级。",
    )

    @field_validator("search_queries")
    @classmethod
    def validate_search_queries(cls, queries: list[str]) -> list[str]:
        """
        确保查询不为空且不存在重复项。
        """
        normalized_queries = [
            query.strip()
            for query in queries
            if query.strip()
        ]

        if len(normalized_queries) != len(queries):
            raise ValueError("search_queries 中不能包含空字符串。")

        normalized_query_keys = {
            query.lower()
            for query in normalized_queries
        }

        if len(normalized_query_keys) != len(normalized_queries):
            raise ValueError("search_queries 中不能包含重复查询。")

        return normalized_queries


class PlannerOutput(BaseModel):
    """
    Planner Agent 直接输出的结构化研究计划。

    不包含 task_id、plan_id、created_at 等系统字段，
    因为这些字段应由服务端生成。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "plan_title": "企业 AI Agent 客服应用研究计划",
                    "overall_strategy": (
                        "从业务价值、主要风险和落地路径三个维度展开，"
                        "优先使用官方文档和行业报告。"
                    ),
                    "subtasks": [
                        {
                            "subtask_id": "subtask_1",
                            "title": "客服场景的业务价值",
                            "research_question": (
                                "企业在客户服务场景中使用 AI Agent "
                                "可以带来哪些可量化的业务价值？"
                            ),
                            "objective": (
                                "识别效率、成本、客户体验等维度的收益，"
                                "并收集相关证据。"
                            ),
                            "search_queries": [
                                "AI agent customer service ROI",
                                "customer service automation metrics",
                            ],
                            "preferred_source_types": [
                                "OFFICIAL_DOCUMENT",
                                "INDUSTRY_REPORT",
                            ],
                            "priority": 1,
                        },
                        {
                            "subtask_id": "subtask_2",
                            "title": "客服 AI Agent 的主要风险",
                            "research_question": (
                                "企业部署客服 AI Agent 时，"
                                "主要面临哪些技术、合规和运营风险？"
                            ),
                            "objective": (
                                "梳理数据安全、幻觉、人工兜底和合规风险。"
                            ),
                            "search_queries": [
                                "AI agent customer service risks",
                                "AI customer service compliance risks",
                            ],
                            "preferred_source_types": [
                                "OFFICIAL_DOCUMENT",
                                "NEWS",
                            ],
                            "priority": 1,
                        },
                    ],
                }
            ]
        }
    )

    plan_title: str = Field(
        ...,
        min_length=8,
        max_length=150,
        description="研究计划标题。",
    )
    overall_strategy: str = Field(
        ...,
        min_length=20,
        max_length=500,
        description="Planner 对研究路径的总体说明。",
    )
    subtasks: list[ResearchSubTask] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="拆分后的研究子任务列表。",
    )

    @model_validator(mode="after")
    def validate_subtasks(self) -> "PlannerOutput":
        """
        确保子任务 ID 唯一，且优先级中至少存在一个最高优先级任务。
        """
        subtask_ids = [
            subtask.subtask_id
            for subtask in self.subtasks
        ]

        if len(subtask_ids) != len(set(subtask_ids)):
            raise ValueError("subtask_id 必须唯一。")

        priorities = [
            subtask.priority
            for subtask in self.subtasks
        ]

        if 1 not in priorities:
            raise ValueError("研究计划至少需要一个 priority 为 1 的子任务。")

        return self


class ResearchPlanResponse(PlannerOutput):
    """
    保存后的研究计划。

    系统字段由服务端生成，而不是由 Planner Agent 生成。
    """

    plan_id: UUID = Field(
        ...,
        description="研究计划唯一标识。",
    )
    task_id: UUID = Field(
        ...,
        description="所属研究任务的唯一标识。",
    )
    created_at: datetime = Field(
        ...,
        description="研究计划创建时间。",
    )