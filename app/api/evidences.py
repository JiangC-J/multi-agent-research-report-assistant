from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.repositories.sqlite_evidence_repository import (
    SQLiteEvidenceRepository,
)
from app.repositories.sqlite_research_plan_repository import (
    SQLiteResearchPlanRepository,
)
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.evidence import EvidenceDraft, EvidenceResponse
from app.services.evidence_service import (
    DuplicateEvidenceError,
    EvidencePlanNotFoundError,
    EvidenceService,
    EvidenceTaskStatusMismatchError,
    ResearchSubTaskNotFoundError,
)
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


router = APIRouter(
    tags=["evidences"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

plan_repository = SQLiteResearchPlanRepository()
evidence_repository = SQLiteEvidenceRepository()

evidence_service = EvidenceService(
    task_service=task_service,
    plan_repository=plan_repository,
    evidence_repository=evidence_repository,
)


@router.post(
    "/research-tasks/{task_id}/subtasks/{subtask_id}/evidences",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="保存证据（开发调试）",
)
async def create_evidence(
    task_id: UUID,
    subtask_id: str,
    payload: EvidenceDraft,
) -> EvidenceResponse:
    """
    当前用于模拟 Researcher 保存检索结果。

    后续由 Researcher Agent 自动调用。
    """
    try:
        return evidence_service.create_evidence(
            task_id=task_id,
            subtask_id=subtask_id,
            payload=payload,
        )
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ResearchSubTaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (
        EvidenceTaskStatusMismatchError,
        EvidencePlanNotFoundError,
        DuplicateEvidenceError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "/research-tasks/{task_id}/evidences",
    response_model=list[EvidenceResponse],
    summary="查询任务全部证据",
)
async def list_evidences(
    task_id: UUID,
) -> list[EvidenceResponse]:
    """
    查询指定研究任务保存的全部证据。
    """
    try:
        return evidence_service.list_evidences_by_task_id(task_id)
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error