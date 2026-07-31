from uuid import UUID

from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.claim_repository import ClaimRepository
from app.repositories.review_repository import ReviewRepository
from app.schemas.agent_run import AgentName, AgentRunStatus
from app.schemas.claim import ClaimReviewStatus
from app.schemas.review import ReviewDecision
from app.schemas.review_decision import (
    TaskReviewDecisionResponse,
    TaskReviewOutcome,
)
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class ReviewAggregationTaskStatusMismatchError(Exception):
    """
    任务不处于 REVIEWING 状态时抛出。
    """


class PendingClaimExistsError(Exception):
    """
    仍存在未审核 Claim 时抛出。
    """


class ReviewAggregationService:
    """
    根据全部 Claim 审核结果决定任务下一步状态。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        claim_repository: ClaimRepository,
        review_repository: ReviewRepository,
        agent_run_repository: AgentRunRepository,
        max_review_iterations: int = 2,
    ) -> None:
        self._task_service = task_service
        self._claim_repository = claim_repository
        self._review_repository = review_repository
        self._agent_run_repository = agent_run_repository
        self._max_review_iterations = max_review_iterations

    def decide_next_step(
        self,
        task_id: UUID,
    ) -> TaskReviewDecisionResponse:
        """
        汇总审核结果，并推动任务进入下一阶段。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.REVIEWING:
            raise ReviewAggregationTaskStatusMismatchError(
                "只有 REVIEWING 状态的任务可以进行审核汇总；"
                f"当前状态为 {task.status.value}。"
            )

        claims = self._claim_repository.list_by_task_id(task_id)

        if not claims:
            return self._mark_task_failed(
                task_id=task_id,
                review_iteration=0,
                approved_count=0,
                needs_revision_count=0,
                rejected_count=0,
                message="任务没有可供审核的 Claim，无法生成报告。",
            )

        pending_claims = [
            claim
            for claim in claims
            if claim.review_status == ClaimReviewStatus.PENDING
        ]

        if pending_claims:
            raise PendingClaimExistsError(
                "仍存在 PENDING Claim，请先完成 Reviewer 审核。"
            )

        approved_claims = [
            claim
            for claim in claims
            if claim.review_status == ClaimReviewStatus.APPROVED
        ]
        needs_revision_claims = [
            claim
            for claim in claims
            if claim.review_status == ClaimReviewStatus.NEEDS_REVISION
        ]
        rejected_claims = [
            claim
            for claim in claims
            if claim.review_status == ClaimReviewStatus.REJECTED
        ]

        review_iteration = self._count_review_iterations(task_id)

        approved_count = len(approved_claims)
        needs_revision_count = len(needs_revision_claims)
        rejected_count = len(rejected_claims)

        if needs_revision_claims:
            required_actions = self._collect_required_actions(
                needs_revision_claims
            )

            if review_iteration < self._max_review_iterations:
                self._task_service.transition_task_status(
                    task_id=task_id,
                    payload=TaskStatusUpdate(
                        status=TaskStatus.RESEARCHING,
                    ),
                )

                return TaskReviewDecisionResponse(
                    outcome=TaskReviewOutcome.RETURN_TO_RESEARCH,
                    review_iteration=review_iteration,
                    max_review_iterations=self._max_review_iterations,
                    approved_count=approved_count,
                    needs_revision_count=needs_revision_count,
                    rejected_count=rejected_count,
                    required_actions=required_actions,
                    message=(
                        "存在需要补充或修改的 Claim，"
                        "任务将返回 RESEARCHING 阶段。"
                    ),
                )

            if approved_count > 0:
                self._task_service.transition_task_status(
                    task_id=task_id,
                    payload=TaskStatusUpdate(
                        status=TaskStatus.WRITING,
                    ),
                )

                return TaskReviewDecisionResponse(
                    outcome=TaskReviewOutcome.PROCEED_TO_WRITING,
                    review_iteration=review_iteration,
                    max_review_iterations=self._max_review_iterations,
                    approved_count=approved_count,
                    needs_revision_count=needs_revision_count,
                    rejected_count=rejected_count,
                    required_actions=required_actions,
                    message=(
                        "已达到最大审核轮次，将生成降级报告；"
                        "报告仅使用 APPROVED Claim。"
                    ),
                )

            return self._mark_task_failed(
                task_id=task_id,
                review_iteration=review_iteration,
                approved_count=approved_count,
                needs_revision_count=needs_revision_count,
                rejected_count=rejected_count,
                message=(
                    "已达到最大审核轮次，且没有 APPROVED Claim，"
                    "无法生成可信报告。"
                ),
            )

        if approved_count > 0:
            self._task_service.transition_task_status(
                task_id=task_id,
                payload=TaskStatusUpdate(
                    status=TaskStatus.WRITING,
                ),
            )

            return TaskReviewDecisionResponse(
                outcome=TaskReviewOutcome.PROCEED_TO_WRITING,
                review_iteration=review_iteration,
                max_review_iterations=self._max_review_iterations,
                approved_count=approved_count,
                needs_revision_count=needs_revision_count,
                rejected_count=rejected_count,
                required_actions=[],
                message=(
                    "所有待处理 Claim 已审核完成，"
                    "任务可以进入 WRITING 阶段。"
                ),
            )

        return self._mark_task_failed(
            task_id=task_id,
            review_iteration=review_iteration,
            approved_count=approved_count,
            needs_revision_count=needs_revision_count,
            rejected_count=rejected_count,
            message="没有 APPROVED Claim，无法生成可信报告。",
        )

    def _count_review_iterations(
        self,
        task_id: UUID,
    ) -> int:
        """
        从成功的 Reviewer AgentRun 推导审核轮次。
        """
        agent_runs = self._agent_run_repository.list_by_task_id(
            task_id
        )

        return sum(
            agent_run.agent_name == AgentName.REVIEWER
            and agent_run.status == AgentRunStatus.SUCCEEDED
            for agent_run in agent_runs
        )

    def _collect_required_actions(
        self,
        needs_revision_claims,
    ) -> list[str]:
        """
        汇总 NEEDS_REVISION Claim 最近一次审核中的返工动作。
        """
        unique_actions: list[str] = []

        for claim in needs_revision_claims:
            reviews = self._review_repository.list_by_claim_id(
                claim.claim_id
            )

            if not reviews:
                continue

            latest_review = reviews[-1]

            if latest_review.decision != ReviewDecision.NEEDS_REVISION:
                continue

            for action in latest_review.required_actions:
                if action not in unique_actions:
                    unique_actions.append(action)

        return unique_actions

    def _mark_task_failed(
        self,
        task_id: UUID,
        review_iteration: int,
        approved_count: int,
        needs_revision_count: int,
        rejected_count: int,
        message: str,
    ) -> TaskReviewDecisionResponse:
        """
        标记任务失败，并返回统一的失败决策结果。
        """
        self._task_service.transition_task_status(
            task_id=task_id,
            payload=TaskStatusUpdate(
                status=TaskStatus.FAILED,
                error_message=message,
            ),
        )

        return TaskReviewDecisionResponse(
            outcome=TaskReviewOutcome.FAILED,
            review_iteration=review_iteration,
            max_review_iterations=self._max_review_iterations,
            approved_count=approved_count,
            needs_revision_count=needs_revision_count,
            rejected_count=rejected_count,
            required_actions=[],
            message=message,
        )