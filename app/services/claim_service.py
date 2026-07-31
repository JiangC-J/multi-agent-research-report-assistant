from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.repositories.claim_repository import ClaimRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.claim import (
    ClaimDraft,
    ClaimResponse,
    ClaimReviewStatus,
)
from app.schemas.research_task import TaskStatus
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class ClaimTaskStatusMismatchError(Exception):
    """
    任务不处于 ANALYZING 状态时抛出。
    """


class InvalidClaimEvidenceReferenceError(Exception):
    """
    Claim 引用了不存在或不属于当前任务的 Evidence 时抛出。
    """


class ClaimService:
    """
    结论的业务服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        evidence_repository: EvidenceRepository,
        claim_repository: ClaimRepository,
    ) -> None:
        self._task_service = task_service
        self._evidence_repository = evidence_repository
        self._claim_repository = claim_repository

    def create_claim(
        self,
        task_id: UUID,
        payload: ClaimDraft,
    ) -> ClaimResponse:
        """
        校验并保存一条基于 Evidence 的结论。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.ANALYZING:
            raise ClaimTaskStatusMismatchError(
                "只有 ANALYZING 状态的任务可以保存结论；"
                f"当前状态为 {task.status.value}。"
            )

        task_evidences = self._evidence_repository.list_by_task_id(task_id)

        available_evidence_ids = {
            evidence.evidence_id
            for evidence in task_evidences
        }

        invalid_evidence_ids = [
            evidence_id
            for evidence_id in payload.evidence_ids
            if evidence_id not in available_evidence_ids
        ]

        if invalid_evidence_ids:
            invalid_id_text = ", ".join(
                str(evidence_id)
                for evidence_id in invalid_evidence_ids
            )
            raise InvalidClaimEvidenceReferenceError(
                "以下 evidence_id 不存在或不属于当前任务："
                f"{invalid_id_text}"
            )

        claim = ClaimResponse(
            claim_id=uuid4(),
            task_id=task_id,
            claim_text=payload.claim_text,
            claim_type=payload.claim_type,
            evidence_ids=payload.evidence_ids,
            evidence_rationale=payload.evidence_rationale,
            confidence_score=payload.confidence_score,
            limitations=payload.limitations,
            created_at=datetime.now(timezone.utc),
            review_status=ClaimReviewStatus.PENDING,
        )

        return self._claim_repository.create(claim)

    def list_claims_by_task_id(
        self,
        task_id: UUID,
    ) -> list[ClaimResponse]:
        """
        查询一个研究任务的全部结论。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        return self._claim_repository.list_by_task_id(task_id)