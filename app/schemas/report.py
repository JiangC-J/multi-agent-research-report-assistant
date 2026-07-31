from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReportSectionType(str, Enum):
    """
    报告章节类型。
    """

    EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
    KEY_FINDINGS = "KEY_FINDINGS"
    RISKS = "RISKS"
    RECOMMENDATIONS = "RECOMMENDATIONS"
    LIMITATIONS = "LIMITATIONS"


class ReportStatus(str, Enum):
    """
    报告生成状态。
    """

    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"


class ReportSectionDraft(BaseModel):
    """
    Writer 生成的一段报告章节内容。

    每个章节必须关联已审核通过的 Claim。
    """

    section_type: ReportSectionType = Field(
        ...,
        description="报告章节类型。",
    )
    heading: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="章节标题。",
    )
    content: str = Field(
        ...,
        min_length=20,
        max_length=4000,
        description="章节正文内容，不应新增未经审核的事实。",
    )
    claim_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="本章节使用的已审核通过 Claim ID 列表。",
    )

    @field_validator("heading", "content")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        """
        清理文本首尾空白，阻止纯空白内容。
        """
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("文本字段不能只包含空白字符。")

        return cleaned_value

    @field_validator("claim_ids")
    @classmethod
    def validate_claim_ids(
        cls,
        claim_ids: list[UUID],
    ) -> list[UUID]:
        """
        防止同一章节重复引用同一条 Claim。
        """
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_ids 中不能包含重复结论。")

        return claim_ids


class ReportCitationDraft(BaseModel):
    """
    报告中的一条来源引用。

    citation_key 会被 Markdown 渲染器用于生成 [1]、[2] 等引用标记。
    """

    citation_key: str = Field(
        ...,
        pattern=r"^source_[1-9][0-9]*$",
        description="引用标识，例如 source_1。",
    )
    evidence_id: UUID = Field(
        ...,
        description="引用对应的 Evidence ID。",
    )
    claim_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="该来源支撑的 Claim ID 列表。",
    )

    @field_validator("claim_ids")
    @classmethod
    def validate_claim_ids(
        cls,
        claim_ids: list[UUID],
    ) -> list[UUID]:
        """
        防止一条引用重复关联同一 Claim。
        """
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_ids 中不能包含重复结论。")

        return claim_ids


class ReportDraft(BaseModel):
    """
    Writer 输出的结构化报告内容。

    不包含 report_id、task_id、状态、创建时间和 Markdown，
    这些字段由服务端生成。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "report_title": "企业 AI Agent 客服应用研究报告",
                    "sections": [
                        {
                            "section_type": "EXECUTIVE_SUMMARY",
                            "heading": "执行摘要",
                            "content": (
                                "企业应优先在高重复、规则相对明确且"
                                "能够人工兜底的客服流程中试点 AI Agent。"
                            ),
                            "claim_ids": [
                                "11111111-1111-1111-1111-111111111111"
                            ],
                        },
                        {
                            "section_type": "RECOMMENDATIONS",
                            "heading": "落地建议",
                            "content": (
                                "建议先选择标准化程度较高的流程进行小范围试点，"
                                "并配置人工升级与异常处理机制。"
                            ),
                            "claim_ids": [
                                "11111111-1111-1111-1111-111111111111"
                            ],
                        },
                    ],
                    "citations": [
                        {
                            "citation_key": "source_1",
                            "evidence_id": (
                                "22222222-2222-2222-2222-222222222222"
                            ),
                            "claim_ids": [
                                "11111111-1111-1111-1111-111111111111"
                            ],
                        }
                    ],
                }
            ]
        }
    )

    report_title: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="报告标题。",
    )
    sections: list[ReportSectionDraft] = Field(
        ...,
        min_length=2,
        max_length=6,
        description="报告章节列表。",
    )
    citations: list[ReportCitationDraft] = Field(
        ...,
        min_length=1,
        max_length=30,
        description="报告引用列表。",
    )

    @field_validator("report_title")
    @classmethod
    def validate_report_title(cls, value: str) -> str:
        """
        清理标题首尾空白。
        """
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("报告标题不能只包含空白字符。")

        return cleaned_value

    @model_validator(mode="after")
    def validate_report_structure(self) -> "ReportDraft":
        """
        确保章节类型和引用标识均不重复。
        """
        section_types = [
            section.section_type
            for section in self.sections
        ]

        if len(section_types) != len(set(section_types)):
            raise ValueError("同一种报告章节类型只能出现一次。")

        citation_keys = [
            citation.citation_key
            for citation in self.citations
        ]

        if len(citation_keys) != len(set(citation_keys)):
            raise ValueError("citation_key 必须唯一。")

        return self


class ReportResponse(ReportDraft):
    """
    保存后的最终报告。

    markdown_content 由服务端根据结构化章节与引用统一渲染。
    """

    report_id: UUID = Field(
        ...,
        description="报告唯一标识。",
    )
    task_id: UUID = Field(
        ...,
        description="所属研究任务唯一标识。",
    )
    status: ReportStatus = Field(
        ...,
        description="报告状态。",
    )
    markdown_content: str = Field(
        ...,
        description="最终渲染的 Markdown 报告。",
    )
    created_at: datetime = Field(
        ...,
        description="报告创建时间。",
    )