from typing import Protocol
from uuid import UUID

from app.schemas.review import ClaimReviewResponse


class ReviewRepository(Protocol):
    """
    Claim 审核记录的数据访问约定。
    """

    def create(
        self,
        review: ClaimReviewResponse,
    ) -> ClaimReviewResponse:
        """
        保存一条新的审核记录。
        """

    def list_by_claim_id(
        self,
        claim_id: UUID,
    ) -> list[ClaimReviewResponse]:
        """
        查询一条 Claim 的全部审核历史。
        """