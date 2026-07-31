from pydantic import BaseModel, Field

from app.schemas.review import ClaimReviewResponse


class ReviewerExecutionResponse(BaseModel):
    """
    Reviewer 批量审核 PENDING Claim 后的结果。
    """

    reviews: list[ClaimReviewResponse] = Field(
        default_factory=list,
        description="本次创建的审核记录。",
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