from enum import Enum

from pydantic import BaseModel, Field


class TaskReviewOutcome(str, Enum):
    """
    任务级审核后可进入的下一步。
    """

    RETURN_TO_RESEARCH = "RETURN_TO_RESEARCH"
    PROCEED_TO_WRITING = "PROCEED_TO_WRITING"
    FAILED = "FAILED"


class TaskReviewDecisionResponse(BaseModel):
    """
    任务级审核汇总结果。
    """

    outcome: TaskReviewOutcome = Field(
        ...,
        description="任务审核后的下一步动作。",
    )
    review_iteration: int = Field(
        ...,
        ge=0,
        description="当前已完成的 Reviewer 审核轮次。",
    )
    max_review_iterations: int = Field(
        ...,
        ge=1,
        description="允许的最大 Reviewer 审核轮次。",
    )
    approved_count: int = Field(
        ...,
        ge=0,
        description="审核通过的 Claim 数量。",
    )
    needs_revision_count: int = Field(
        ...,
        ge=0,
        description="需要补充或修改的 Claim 数量。",
    )
    rejected_count: int = Field(
        ...,
        ge=0,
        description="被拒绝的 Claim 数量。",
    )
    required_actions: list[str] = Field(
        default_factory=list,
        description="返工时需要交给 Researcher 的具体动作。",
    )
    message: str = Field(
        ...,
        description="本次任务级决策说明。",
    )