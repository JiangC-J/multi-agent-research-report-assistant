from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.repositories.claim_repository import ClaimRepository
from app.repositories.review_repository import ReviewRepository
from app.schemas.claim import ClaimReviewStatus
from app.schemas.research_task import TaskStatus
from app.schemas.review import (
    ClaimReviewDraft,
    ClaimReviewResponse,
    ReviewDecision,
)
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class ReviewTaskStatusMismatchError(Exception):
    """
    任务不处于 REVIEWING 状态时抛出。
    """


class ClaimNotFoundError(Exception):
    """
    Claim 不存在或不属于当前任务时抛出。
    """


class ClaimAlreadyReviewedError(Exception):
    """
    Claim 不再是 PENDING 状态时抛出。
    """


class InvalidReviewEvidenceReferenceError(Exception):
    """
    Reviewer 核验了不属于当前 Claim 的 Evidence 时抛出。
    """


class ReviewService:
    """
    Claim 审核的业务服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        claim_repository: ClaimRepository,
        review_repository: ReviewRepository,
    ) -> None:
        self._task_service = task_service
        self._claim_repository = claim_repository
        self._review_repository = review_repository

    def create_review(
        self,
        task_id: UUID,
        claim_id: UUID,
        payload: ClaimReviewDraft,
    ) -> ClaimReviewResponse:
        """
        审核一条 PENDING Claim，并更新其当前审核状态。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.REVIEWING:
            raise ReviewTaskStatusMismatchError(
                "只有 REVIEWING 状态的任务可以审核结论；"
                f"当前状态为 {task.status.value}。"
            )

        claim = self._claim_repository.get_by_id(claim_id)

        if claim is None or claim.task_id != task_id:
            raise ClaimNotFoundError("当前任务中不存在该结论。")

        if claim.review_status != ClaimReviewStatus.PENDING:
            raise ClaimAlreadyReviewedError(
                "只有 PENDING 状态的结论可以进行首次审核。"
            )

        claim_evidence_ids = set(claim.evidence_ids)

        invalid_verified_evidence_ids = [
            evidence_id
            for evidence_id in payload.verified_evidence_ids
            if evidence_id not in claim_evidence_ids
        ]

        issue_evidence_ids = {
            evidence_id
            for issue in payload.issues
            for evidence_id in issue.related_evidence_ids
        }

        invalid_issue_evidence_ids = (
            issue_evidence_ids - claim_evidence_ids
        )

        if (
            invalid_verified_evidence_ids
            or invalid_issue_evidence_ids
        ):
            raise InvalidReviewEvidenceReferenceError(
                "Reviewer 只能核验或引用当前 Claim 已绑定的 Evidence。"
            )

        review = ClaimReviewResponse(
            review_id=uuid4(),
            task_id=task_id,
            claim_id=claim_id,
            decision=payload.decision,
            evidence_assessment=payload.evidence_assessment,
            verified_evidence_ids=payload.verified_evidence_ids,
            review_comment=payload.review_comment,
            issues=payload.issues,
            required_actions=payload.required_actions,
            reviewed_at=datetime.now(timezone.utc),
        )

        saved_review = self._review_repository.create(review)

        review_status = ClaimReviewStatus(payload.decision.value)

        self._claim_repository.update_review_status(
            claim_id=claim_id,
            review_status=review_status,
            review_comment=payload.review_comment,
        )

        return saved_review

    def list_reviews_by_claim_id(
        self,
        task_id: UUID,
        claim_id: UUID,
    ) -> list[ClaimReviewResponse]:
        """
        查询某条 Claim 的审核历史。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        claim = self._claim_repository.get_by_id(claim_id)

        if claim is None or claim.task_id != task_id:
            raise ClaimNotFoundError("当前任务中不存在该结论。")

        return self._review_repository.list_by_claim_id(claim_id)