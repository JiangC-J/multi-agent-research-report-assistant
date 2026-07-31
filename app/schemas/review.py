from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReviewDecision(str, Enum):
    """
    Reviewer 对 Claim 作出的最终审核决定。
    """

    APPROVED = "APPROVED"
    NEEDS_REVISION = "NEEDS_REVISION"
    REJECTED = "REJECTED"


class EvidenceAssessment(str, Enum):
    """
    Reviewer 对 Evidence 支撑程度的判断。
    """

    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTING = "CONFLICTING"


class ReviewIssueType(str, Enum):
    """
    Reviewer 发现的问题类型。
    """

    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    LOW_SOURCE_QUALITY = "LOW_SOURCE_QUALITY"
    IRRELEVANT_EVIDENCE = "IRRELEVANT_EVIDENCE"
    OVERCLAIMING = "OVERCLAIMING"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    OUTDATED_EVIDENCE = "OUTDATED_EVIDENCE"


class ReviewIssue(BaseModel):
    """
    一条具体的审核问题。
    """

    issue_type: ReviewIssueType = Field(
        ...,
        description="问题分类。",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=600,
        description="问题的具体说明。",
    )
    related_evidence_ids: list[UUID] = Field(
        default_factory=list,
        max_length=5,
        description="与问题相关的 Evidence ID。",
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        """
        清理问题说明首尾空白。
        """
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("问题说明不能只包含空白字符。")

        return cleaned_value

    @field_validator("related_evidence_ids")
    @classmethod
    def validate_related_evidence_ids(
        cls,
        evidence_ids: list[UUID],
    ) -> list[UUID]:
        """
        防止同一问题重复关联相同 Evidence。
        """
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError(
                "related_evidence_ids 中不能包含重复证据。"
            )

        return evidence_ids


class ClaimReviewDraft(BaseModel):
    """
    Reviewer 对一条 Claim 的审核结果。

    不包含 review_id、task_id、claim_id、reviewed_at 等系统字段，
    这些字段由服务端生成。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "decision": "NEEDS_REVISION",
                    "evidence_assessment": "INSUFFICIENT",
                    "verified_evidence_ids": [
                        "11111111-1111-1111-1111-111111111111"
                    ],
                    "review_comment": (
                        "当前证据能够说明重复性客服工作可被部分自动化，"
                        "但不足以直接推出适用于所有客服流程的部署建议。"
                    ),
                    "issues": [
                        {
                            "issue_type": "OVERCLAIMING",
                            "description": (
                                "结论的适用范围过宽，"
                                "应限定为规则明确且有人工兜底的流程。"
                            ),
                            "related_evidence_ids": [
                                "11111111-1111-1111-1111-111111111111"
                            ],
                        }
                    ],
                    "required_actions": [
                        "补充不同客服场景的案例资料。",
                        "在结论中明确人工升级机制的适用前提。"
                    ],
                }
            ]
        }
    )

    decision: ReviewDecision = Field(
        ...,
        description="Reviewer 的审核决定。",
    )
    evidence_assessment: EvidenceAssessment = Field(
        ...,
        description="Reviewer 对证据充分性的判断。",
    )
    verified_evidence_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Reviewer 实际核验过的 Evidence ID。",
    )
    review_comment: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="审核结论说明。",
    )
    issues: list[ReviewIssue] = Field(
        default_factory=list,
        max_length=5,
        description="审核发现的问题列表。",
    )
    required_actions: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="需要补充研究或修改结论时的具体动作。",
    )

    @field_validator("review_comment")
    @classmethod
    def validate_review_comment(cls, value: str) -> str:
        """
        清理审核说明首尾空白。
        """
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("审核说明不能只包含空白字符。")

        return cleaned_value

    @field_validator("verified_evidence_ids")
    @classmethod
    def validate_verified_evidence_ids(
        cls,
        evidence_ids: list[UUID],
    ) -> list[UUID]:
        """
        防止重复核验同一条 Evidence。
        """
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError(
                "verified_evidence_ids 中不能包含重复证据。"
            )

        return evidence_ids

    @field_validator("required_actions")
    @classmethod
    def validate_required_actions(
        cls,
        actions: list[str],
    ) -> list[str]:
        """
        清理动作描述，阻止空字符串。
        """
        cleaned_actions = [
            action.strip()
            for action in actions
            if action.strip()
        ]

        if len(cleaned_actions) != len(actions):
            raise ValueError(
                "required_actions 中不能包含空字符串。"
            )

        return cleaned_actions

    @model_validator(mode="after")
    def normalize_review_result(self) -> "ClaimReviewDraft":
        """
        校验并保守修复模型可能输出的矛盾审核结果。

        核心安全规则：
        只要审核字段出现矛盾，系统绝不保留 APPROVED，
        而是降级为 NEEDS_REVISION。
        """

        # APPROVED 必须同时满足：
        # 1. 证据评估为 SUFFICIENT；
        # 2. 没有需要处理的问题；
        # 3. 没有要求返工的动作。
        approved_is_inconsistent = (
            self.decision == ReviewDecision.APPROVED
            and (
                self.evidence_assessment
                != EvidenceAssessment.SUFFICIENT
                or bool(self.issues)
                or bool(self.required_actions)
            )
        )

        if approved_is_inconsistent:
            self.decision = ReviewDecision.NEEDS_REVISION

            self.review_comment = (
                f"{self.review_comment}\n"
                "系统校验：审核结果存在字段矛盾，"
                "已保守降级为 NEEDS_REVISION。"
            )

        # NEEDS_REVISION 必须有问题和后续动作。
        # 如果模型遗漏，系统补充通用且安全的返工要求。
        if self.decision == ReviewDecision.NEEDS_REVISION:
            if not self.issues:
                issue_type = (
                    ReviewIssueType.CONFLICTING_EVIDENCE
                    if self.evidence_assessment
                    == EvidenceAssessment.CONFLICTING
                    else ReviewIssueType.MISSING_EVIDENCE
                )

                self.issues = [
                    ReviewIssue(
                        issue_type=issue_type,
                        description=(
                            "当前审核结果无法充分支持该结论，"
                            "需要补充或重新核验相关证据。"
                        ),
                        related_evidence_ids=(
                            self.verified_evidence_ids
                        ),
                    )
                ]

            if not self.required_actions:
                self.required_actions = [
                    "补充与该结论直接相关的权威来源，"
                    "并重新核验结论与证据之间的对应关系。"
                ]

        # REJECTED 也必须说明拒绝原因。
        if self.decision == ReviewDecision.REJECTED:
            if not self.issues:
                self.issues = [
                    ReviewIssue(
                        issue_type=ReviewIssueType.OVERCLAIMING,
                        description=(
                            "当前结论缺少足够证据支持，"
                            "不应作为最终报告结论保留。"
                        ),
                        related_evidence_ids=(
                            self.verified_evidence_ids
                        ),
                    )
                ]

        return self


class ClaimReviewResponse(ClaimReviewDraft):
    """
    保存后的审核记录。
    """

    review_id: UUID = Field(
        ...,
        description="审核记录唯一标识。",
    )
    task_id: UUID = Field(
        ...,
        description="所属研究任务的唯一标识。",
    )
    claim_id: UUID = Field(
        ...,
        description="被审核结论的唯一标识。",
    )
    reviewed_at: datetime = Field(
        ...,
        description="审核完成时间。",
    )