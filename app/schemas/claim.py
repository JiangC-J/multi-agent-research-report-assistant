from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClaimType(str, Enum):
    """
    研究结论的类型。
    """

    FACTUAL_FINDING = "FACTUAL_FINDING"
    ANALYSIS = "ANALYSIS"
    RISK = "RISK"
    RECOMMENDATION = "RECOMMENDATION"


class ClaimReviewStatus(str, Enum):
    """
    Reviewer 对结论的审核状态。
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    NEEDS_REVISION = "NEEDS_REVISION"
    REJECTED = "REJECTED"


class ClaimDraft(BaseModel):
    """
    Analyst 基于证据生成的结论。

    不包含 claim_id、task_id、created_at、审核状态等系统字段，
    这些字段由服务端生成和管理。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "claim_text": (
                        "企业应优先在高重复、规则相对明确、"
                        "能够人工兜底的客服流程中部署 AI Agent。"
                    ),
                    "claim_type": "RECOMMENDATION",
                    "evidence_ids": [
                        "11111111-1111-1111-1111-111111111111",
                        "22222222-2222-2222-2222-222222222222",
                    ],
                    "evidence_rationale": (
                        "相关证据分别说明了重复性工作自动化的潜在效率收益，"
                        "以及人工升级机制对降低风险的重要性。"
                    ),
                    "confidence_score": 0.82,
                    "limitations": (
                        "该结论主要适用于流程标准化程度较高的客服场景。"
                    ),
                }
            ]
        }
    )

    claim_text: str = Field(
        ...,
        min_length=15,
        max_length=1000,
        description="基于证据得出的研究结论。",
    )
    claim_type: ClaimType = Field(
        ...,
        description="结论类型。",
    )
    evidence_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="支撑该结论的 Evidence ID 列表。",
    )
    evidence_rationale: str = Field(
        ...,
        min_length=10,
        max_length=600,
        description="说明这些证据如何支撑当前结论的简洁理由。",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Analyst 对该结论的初步置信度。",
    )
    limitations: str | None = Field(
        default=None,
        max_length=600,
        description="结论的适用边界、证据不足或潜在限制。",
    )

    @field_validator(
        "claim_text",
        "evidence_rationale",
        "limitations",
    )
    @classmethod
    def validate_text_fields(cls, value: str | None) -> str | None:
        """
        清理文本字段首尾空白，并阻止纯空白内容。
        """
        if value is None:
            return None

        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("文本字段不能只包含空白字符。")

        return cleaned_value

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(
        cls,
        evidence_ids: list[UUID],
    ) -> list[UUID]:
        """
        同一条结论不能重复引用同一条证据。
        """
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence_ids 中不能包含重复证据。")

        return evidence_ids


class ClaimResponse(ClaimDraft):
    """
    保存后的结论记录。

    包含系统生成的 ID、任务关联、创建时间和审核状态。
    """

    claim_id: UUID = Field(
        ...,
        description="结论唯一标识。",
    )
    task_id: UUID = Field(
        ...,
        description="所属研究任务的唯一标识。",
    )
    created_at: datetime = Field(
        ...,
        description="结论创建时间。",
    )
    review_status: ClaimReviewStatus = Field(
        default=ClaimReviewStatus.PENDING,
        description="Reviewer 审核状态。",
    )
    review_comment: str | None = Field(
        default=None,
        description="Reviewer 的审核意见。",
    )

class ClaimAnalysisOutput(BaseModel):
    """
    Analyst Agent 一次输出的结论集合。

    每条 Claim 都必须引用系统提供的 Evidence ID。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "claims": [
                        {
                            "claim_text": (
                                "企业应优先在高重复、规则明确且能够"
                                "人工兜底的客服流程中试点 AI Agent。"
                            ),
                            "claim_type": "RECOMMENDATION",
                            "evidence_ids": [
                                "11111111-1111-1111-1111-111111111111"
                            ],
                            "evidence_rationale": (
                                "该 Evidence 指出，在建立人工升级机制后，"
                                "AI 辅助客服可以减少重复性处理工作。"
                            ),
                            "confidence_score": 0.78,
                            "limitations": (
                                "该结论更适用于流程标准化程度较高的客服场景。"
                            ),
                        }
                    ]
                }
            ]
        }
    )

    claims: list[ClaimDraft] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="基于 Evidence 生成的结论列表。",
    )
