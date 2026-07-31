from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.research_plan_repository import (
    ResearchPlanRepository,
)
from app.schemas.evidence import EvidenceDraft, EvidenceResponse
from app.schemas.research_task import TaskStatus
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class EvidenceTaskStatusMismatchError(Exception):
    """
    任务不处于 RESEARCHING 状态时抛出。
    """


class EvidencePlanNotFoundError(Exception):
    """
    任务尚未拥有研究计划时抛出。
    """


class ResearchSubTaskNotFoundError(Exception):
    """
    指定子任务不属于当前研究计划时抛出。
    """


class DuplicateEvidenceError(Exception):
    """
    同一子任务重复保存同一来源时抛出。
    """


class EvidenceService:
    """
    证据的业务服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        plan_repository: ResearchPlanRepository,
        evidence_repository: EvidenceRepository,
    ) -> None:
        self._task_service = task_service
        self._plan_repository = plan_repository
        self._evidence_repository = evidence_repository

    def create_evidence(
        self,
        task_id: UUID,
        subtask_id: str,
        payload: EvidenceDraft,
    ) -> EvidenceResponse:
        """
        校验并保存一条新证据。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.RESEARCHING:
            raise EvidenceTaskStatusMismatchError(
                "只有 RESEARCHING 状态的任务可以保存证据；"
                f"当前状态为 {task.status.value}。"
            )

        plan = self._plan_repository.get_by_task_id(task_id)

        if plan is None:
            raise EvidencePlanNotFoundError(
                "当前研究任务不存在研究计划。"
            )

        valid_subtask_ids = {
            subtask.subtask_id
            for subtask in plan.subtasks
        }

        if subtask_id not in valid_subtask_ids:
            raise ResearchSubTaskNotFoundError(
                f"{subtask_id} 不属于当前研究计划。"
            )

        source_url = str(payload.source_url)

        if self._evidence_repository.exists_by_task_subtask_and_url(
            task_id=task_id,
            subtask_id=subtask_id,
            source_url=source_url,
        ):
            raise DuplicateEvidenceError(
                "当前子任务已经保存过相同来源链接的证据。"
            )

        evidence = EvidenceResponse(
            evidence_id=uuid4(),
            task_id=task_id,
            subtask_id=subtask_id,
            source_title=payload.source_title,
            source_url=payload.source_url,
            source_type=payload.source_type,
            published_at=payload.published_at,
            evidence_kind=payload.evidence_kind,
            content_excerpt=payload.content_excerpt,
            evidence_summary=payload.evidence_summary,
            relevance_score=payload.relevance_score,
            source_quality_hint=payload.source_quality_hint,
            created_at=datetime.now(timezone.utc),
        )

        return self._evidence_repository.create(evidence)

    def list_evidences_by_task_id(
        self,
        task_id: UUID,
    ) -> list[EvidenceResponse]:
        """
        查询一个任务的全部证据。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        return self._evidence_repository.list_by_task_id(task_id)