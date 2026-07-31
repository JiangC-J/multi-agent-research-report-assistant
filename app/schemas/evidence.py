from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)

from app.schemas.research_plan import SourceType


class SourceQualityHint(str, Enum):
    """
    Researcher 对来源质量的初步判断。

    最终是否可信仍由 Reviewer 结合内容进行审核。
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceKind(str, Enum):
    """
    证据内容的主要类型。
    """

    FACT = "FACT"
    STATISTIC = "STATISTIC"
    CASE_STUDY = "CASE_STUDY"
    REGULATION = "REGULATION"
    EXPERT_OPINION = "EXPERT_OPINION"
    BEST_PRACTICE = "BEST_PRACTICE"


class EvidenceExtractionCandidate(BaseModel):
    """
    Evidence Extraction Agent 从候选资料中选择的潜在证据。

    Agent 只负责选择来源并说明其价值，
    不再负责生成 content_excerpt。

    content_excerpt 由服务端从实际检索到的资料文本中直接生成，
    从架构上保证来源可追溯。
    """

    source_url: HttpUrl = Field(
        ...,
        description="本次检索候选资料中的来源链接。",
    )
    
    evidence_kind: EvidenceKind = Field(
        ...,
        description="证据内容的主要类型。",
    )
    evidence_summary: str = Field(
        ...,
        min_length=10,
        max_length=600,
        description=(
            "说明该来源为何能支持当前子任务。"
            "不得超出候选资料表达的事实范围。"
        ),
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="该来源与当前子任务的相关性分数。",
    )
    source_quality_hint: SourceQualityHint = Field(
        ...,
        description="对来源质量的初步判断。",
    )
    model_config = ConfigDict(
        extra="ignore",
    )

    @field_validator("evidence_kind", mode="before")
    @classmethod
    def normalize_evidence_kind(cls, value: object) -> object:
        """
        将常见的实施指南类标签统一为 BEST_PRACTICE。
        """
        aliases = {
            "GUIDE": EvidenceKind.BEST_PRACTICE.value,
            "GUIDELINE": EvidenceKind.BEST_PRACTICE.value,
            "RECOMMENDATION": EvidenceKind.BEST_PRACTICE.value,
        }

        if isinstance(value, str):
            return aliases.get(value, value)

        return value

    @field_validator("evidence_summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        """
        清理首尾空白，并阻止纯空白摘要。
        """
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("evidence_summary 不能只包含空白字符。")

        return cleaned_value


class EvidenceExtractionOutput(BaseModel):
    """
    Evidence Extraction Agent 的结构化输出。

    Agent 输出“选择哪个来源、为什么选择它”；
    服务端随后从真实检索文本中生成原文摘录。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "evidences": [
                        {
                            "source_url": (
                                "https://example.com/ai-agent-report"
                            ),
                            "source_type": "INDUSTRY_REPORT",
                            "evidence_kind": "STATISTIC",
                            "evidence_summary": (
                                "该资料讨论了企业部署 AI Agent 时的"
                                "人工升级机制与风险控制要求。"
                            ),
                            "relevance_score": 0.91,
                            "source_quality_hint": "MEDIUM",
                        }
                    ]
                }
            ]
        }
    )

    evidences: list[EvidenceExtractionCandidate] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="模型选择出的候选资料。",
    )

    @field_validator("evidences")
    @classmethod
    def deduplicate_source_urls(
        cls,
        evidences: list[EvidenceExtractionCandidate],
    ) -> list[EvidenceExtractionCandidate]:
        """
        同一轮提取中，同一来源 URL 最多保留一条 Evidence。

        保留首次出现的来源，丢弃后续重复来源。
        """
        unique_evidences: list[EvidenceExtractionCandidate] = []
        seen_urls: set[str] = set()

        for evidence in evidences:
            source_url = str(evidence.source_url)

            if source_url in seen_urls:
                continue

            seen_urls.add(source_url)
            unique_evidences.append(evidence)

        if not unique_evidences:
            raise ValueError(
                "Evidence Extraction 至少需要保留一条有效证据。"
            )

        return unique_evidences


class EvidenceDraft(BaseModel):
    """
    Researcher 整理出的单条证据。

    不包含 evidence_id、task_id、subtask_id、created_at 等系统字段，
    这些字段由服务端生成。
    """

    source_title: str = Field(
        ...,
        min_length=3,
        max_length=300,
        description="资料来源标题。",
    )
    source_url: HttpUrl = Field(
        ...,
        description="资料的原始链接。",
    )
    source_type: SourceType = Field(
        ...,
        description="资料来源类型。",
    )
    published_at: datetime | None = Field(
        default=None,
        description="资料发布日期；来源未提供时允许为空。",
    )
    evidence_kind: EvidenceKind = Field(
        ...,
        description="证据主要类型。",
    )
    content_excerpt: str = Field(
        ...,
        min_length=20,
        max_length=3000,
        description="与研究问题直接相关的原文片段或准确摘录。",
    )
    evidence_summary: str = Field(
        ...,
        min_length=10,
        max_length=600,
        description="对该证据的简洁说明，不应超出原文片段表达的范围。",
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="该证据与当前子任务的相关性分数。",
    )
    source_quality_hint: SourceQualityHint = Field(
        ...,
        description="Researcher 对来源质量的初步判断。",
    )

    @field_validator(
        "source_title",
        "content_excerpt",
        "evidence_summary",
    )
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        """
        清理首尾空白，并阻止只包含空白字符的内容。
        """
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("文本字段不能只包含空白字符。")

        return cleaned_value


class EvidenceResponse(EvidenceDraft):
    """
    保存后的证据记录。

    系统字段由服务端生成，用于关联任务、子任务和后续结论。
    """

    evidence_id: UUID = Field(
        ...,
        description="证据唯一标识。",
    )
    task_id: UUID = Field(
        ...,
        description="所属研究任务的唯一标识。",
    )
    subtask_id: str = Field(
        ...,
        pattern=r"^subtask_[1-5]$",
        description="证据所属的研究子任务标识。",
    )
    created_at: datetime = Field(
        ...,
        description="证据保存时间。",
    )
