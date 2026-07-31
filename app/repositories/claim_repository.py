from typing import Protocol
from uuid import UUID

from app.schemas.claim import ClaimResponse, ClaimReviewStatus


class ClaimRepository(Protocol):
    """
    结论数据访问的抽象约定。
    """

    def create(self, claim: ClaimResponse) -> ClaimResponse:
        """
        创建一条结论及其 Evidence 关联。
        """

    def get_by_id(self, claim_id: UUID) -> ClaimResponse | None:
        """
        根据 Claim ID 查询结论。
        """

    def update_review_status(
        self,
        claim_id: UUID,
        review_status: ClaimReviewStatus,
        review_comment: str,
    ) -> ClaimResponse | None:
        """
        更新结论当前审核状态和审核意见。
        """

    def list_by_task_id(self, task_id: UUID) -> list[ClaimResponse]:
        """
        查询一个研究任务的全部结论。
        """