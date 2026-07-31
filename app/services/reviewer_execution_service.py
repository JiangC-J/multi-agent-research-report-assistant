from uuid import UUID

from app.agents.reviewer_agent import ReviewerAgent
from app.repositories.claim_repository import ClaimRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.agent_run import (
    AgentName,
    AgentRunFinish,
    AgentRunStart,
    AgentRunStatus,
)
from app.schemas.claim import ClaimReviewStatus
from app.schemas.reviewer import ReviewerExecutionResponse
from app.schemas.review import ReviewDecision
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.services.agent_run_service import AgentRunService
from app.services.review_service import ReviewService
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class ReviewerTaskStatusMismatchError(Exception):
    """
    任务不处于 REVIEWING 状态时抛出。
    """


class ReviewerExecutionError(Exception):
    """
    Reviewer 执行失败时抛出。
    """


class ReviewerExecutionService:
    """
    Reviewer 批量审核 PENDING Claim 的编排服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        claim_repository: ClaimRepository,
        evidence_repository: EvidenceRepository,
        review_service: ReviewService,
        agent_run_service: AgentRunService,
        reviewer_agent: ReviewerAgent,
    ) -> None:
        self._task_service = task_service
        self._claim_repository = claim_repository
        self._evidence_repository = evidence_repository
        self._review_service = review_service
        self._agent_run_service = agent_run_service
        self._reviewer_agent = reviewer_agent

    async def review_task(
        self,
        task_id: UUID,
    ) -> ReviewerExecutionResponse:
        """
        审核当前任务中全部 PENDING 状态的 Claim。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.REVIEWING:
            raise ReviewerTaskStatusMismatchError(
                "只有 REVIEWING 状态的任务可以执行 Reviewer；"
                f"当前状态为 {task.status.value}。"
            )

        claims = self._claim_repository.list_by_task_id(task_id)

        pending_claims = [
            claim
            for claim in claims
            if claim.review_status == ClaimReviewStatus.PENDING
        ]

        if not pending_claims:
            raise ReviewerExecutionError(
                "当前任务不存在待审核的 PENDING Claim。"
            )

        all_evidences = self._evidence_repository.list_by_task_id(
            task_id
        )
        evidences_by_id = {
            evidence.evidence_id: evidence
            for evidence in all_evidences
        }

        agent_run = self._agent_run_service.start_run(
            task_id=task_id,
            payload=AgentRunStart(
                agent_name=AgentName.REVIEWER,
                input_summary=(
                    f"审核 {len(pending_claims)} 条 PENDING Claim "
                    "与其绑定的 Evidence。"
                ),
            ),
        )

        try:
            reviews = []
            total_input_tokens = 0
            total_output_tokens = 0

            for claim in pending_claims:
                claim_evidences = [
                    evidences_by_id[evidence_id]
                    for evidence_id in claim.evidence_ids
                    if evidence_id in evidences_by_id
                ]

                if len(claim_evidences) != len(claim.evidence_ids):
                    raise RuntimeError(
                        "Claim 绑定的部分 Evidence 无法找到。"
                    )

                agent_result = await self._reviewer_agent.review_claim(
                    claim=claim,
                    evidences=claim_evidences,
                )

                saved_review = self._review_service.create_review(
                    task_id=task_id,
                    claim_id=claim.claim_id,
                    payload=agent_result.review_draft,
                )

                reviews.append(saved_review)
                total_input_tokens += agent_result.input_tokens
                total_output_tokens += agent_result.output_tokens
        except Exception as error:
            error_message = str(error)[:2000]

            self._safe_finish_failed_run(
                run_id=agent_run.run_id,
                error_message=error_message,
            )
            self._safe_mark_task_failed(
                task_id=task_id,
                error_message=error_message,
            )

            raise ReviewerExecutionError(
                "Reviewer 执行失败："
                f"{error_message}"
            ) from error

        approved_count = sum(
            review.decision == ReviewDecision.APPROVED
            for review in reviews
        )
        needs_revision_count = sum(
            review.decision == ReviewDecision.NEEDS_REVISION
            for review in reviews
        )
        rejected_count = sum(
            review.decision == ReviewDecision.REJECTED
            for review in reviews
        )

        self._safe_finish_succeeded_run(
            run_id=agent_run.run_id,
            approved_count=approved_count,
            needs_revision_count=needs_revision_count,
            rejected_count=rejected_count,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )

        return ReviewerExecutionResponse(
            reviews=reviews,
            approved_count=approved_count,
            needs_revision_count=needs_revision_count,
            rejected_count=rejected_count,
        )

    def _safe_finish_succeeded_run(
        self,
        run_id: UUID,
        approved_count: int,
        needs_revision_count: int,
        rejected_count: int,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        尽力记录成功执行指标。
        """
        try:
            self._agent_run_service.finish_run(
                run_id=run_id,
                payload=AgentRunFinish(
                    status=AgentRunStatus.SUCCEEDED,
                    output_summary=(
                        f"审核完成：APPROVED={approved_count}，"
                        f"NEEDS_REVISION={needs_revision_count}，"
                        f"REJECTED={rejected_count}。"
                    ),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=0.0,
                ),
            )
        except Exception:
            pass

    def _safe_finish_failed_run(
        self,
        run_id: UUID,
        error_message: str,
    ) -> None:
        """
        尽力记录失败执行信息。
        """
        try:
            self._agent_run_service.finish_run(
                run_id=run_id,
                payload=AgentRunFinish(
                    status=AgentRunStatus.FAILED,
                    error_message=error_message,
                ),
            )
        except Exception:
            pass

    def _safe_mark_task_failed(
        self,
        task_id: UUID,
        error_message: str,
    ) -> None:
        """
        Reviewer 执行失败时将任务标记为 FAILED。
        """
        try:
            task = self._task_service.get_task(task_id)

            if task is not None and task.status == TaskStatus.REVIEWING:
                self._task_service.transition_task_status(
                    task_id=task_id,
                    payload=TaskStatusUpdate(
                        status=TaskStatus.FAILED,
                        error_message=error_message,
                    ),
                )
        except Exception:
            pass
