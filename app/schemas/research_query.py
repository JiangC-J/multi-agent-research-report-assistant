from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.research_plan import SourceType


class QueryIntent(str, Enum):
    """
    检索查询的主要目的。
    """

    GENERAL_DISCOVERY = "GENERAL_DISCOVERY"
    FACT_VERIFICATION = "FACT_VERIFICATION"
    CASE_STUDY = "CASE_STUDY"
    RISK_AND_COMPLIANCE = "RISK_AND_COMPLIANCE"


class RewrittenQuery(BaseModel):
    """
    一条经过改写、可交给检索工具执行的查询。
    """

    query: str = Field(
        ...,
        min_length=3,
        max_length=300,
        description="用于检索工具的具体查询语句。",
    )
    intent: QueryIntent = Field(
        ...,
        description="本查询的检索目的。",
    )
    rationale: str = Field(
        ...,
        min_length=10,
        max_length=300,
        description="说明该查询为什么有助于完成当前子任务。",
    )
    preferred_source_types: list[SourceType] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="该查询优先寻找的资料类型。",
    )

    @field_validator("intent", mode="before")
    @classmethod
    def normalize_intent(cls, value: object) -> object:
        """
        修正模型把“来源类型”误填到“查询意图”的常见错误。

        该归一化只处理含义明确的枚举映射，不修改查询文本或事实。
        """
        source_type_to_intent = {
            SourceType.OFFICIAL_DOCUMENT.value: (
                QueryIntent.FACT_VERIFICATION.value
            ),
            SourceType.ACADEMIC_PAPER.value: (
                QueryIntent.FACT_VERIFICATION.value
            ),
            SourceType.INDUSTRY_REPORT.value: (
                QueryIntent.GENERAL_DISCOVERY.value
            ),
            SourceType.NEWS.value: (
                QueryIntent.GENERAL_DISCOVERY.value
            ),
        }

        if isinstance(value, str):
            return source_type_to_intent.get(value, value)

        return value

    @field_validator("query", "rationale")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        """
        清理首尾空白，阻止纯空白内容。
        """
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("文本字段不能只包含空白字符。")

        return cleaned_value


class QueryRewriteOutput(BaseModel):
    """
    Query Rewrite Agent 的结构化输出。

    系统已知当前 task_id 和 subtask_id，
    因此模型不负责生成这些系统关联字段。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "queries": [
                        {
                            "query": "AI agent customer service ROI metrics",
                            "intent": "FACT_VERIFICATION",
                            "rationale": (
                                "用于寻找客服 AI Agent 的成本、效率和"
                                "客户体验等量化指标。"
                            ),
                            "preferred_source_types": [
                                "INDUSTRY_REPORT",
                                "OFFICIAL_DOCUMENT"
                            ]
                        },
                        {
                            "query": (
                                "AI customer service agent implementation "
                                "case study"
                            ),
                            "intent": "CASE_STUDY",
                            "rationale": (
                                "用于寻找企业部署客服 AI Agent 的"
                                "真实案例与实施条件。"
                            ),
                            "preferred_source_types": [
                                "CASE_STUDY"
                            ]
                        }
                    ]
                }
            ]
        }
    )

    queries: list[RewrittenQuery] = Field(
        ...,
        # 多查询是检索质量增强项，不应成为长任务的单点故障。
        # 模型提示词仍要求 2 到 3 条；若模型只返回 1 条合法查询，
        # 系统允许降级为单查询检索并继续工作流。
        min_length=1,
        max_length=4,
        description="针对当前子任务改写出的检索查询列表。",
    )

    @model_validator(mode="after")
    def validate_queries(self) -> "QueryRewriteOutput":
        """
        确保查询不重复，且至少包含一个事实核验或案例查询。
        """
        normalized_queries = [
            item.query.lower()
            for item in self.queries
        ]

        if len(normalized_queries) != len(set(normalized_queries)):
            raise ValueError("queries 中不能包含重复查询。")

        useful_intents = {
            QueryIntent.FACT_VERIFICATION,
            QueryIntent.CASE_STUDY,
        }

        if not any(
            item.intent in useful_intents
            for item in self.queries
        ):
            raise ValueError(
                "查询中至少需要包含一条 FACT_VERIFICATION "
                "或 CASE_STUDY 类型的查询。"
            )

        return self
