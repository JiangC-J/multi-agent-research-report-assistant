from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.repositories.sqlite_claim_repository import SQLiteClaimRepository
from app.repositories.sqlite_evidence_repository import (
    SQLiteEvidenceRepository,
)
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.claim import ClaimDraft, ClaimResponse
from app.services.claim_service import (
    ClaimService,
    ClaimTaskStatusMismatchError,
    InvalidClaimEvidenceReferenceError,
)
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/claims",
    tags=["claims"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

evidence_repository = SQLiteEvidenceRepository()
claim_repository = SQLiteClaimRepository()

claim_service = ClaimService(
    task_service=task_service,
    evidence_repository=evidence_repository,
    claim_repository=claim_repository,
)


@router.post(
    "",
    response_model=ClaimResponse,
    status_code=status.HTTP_201_CREATED,
    summary="保存结论（开发调试）",
)
async def create_claim(
    task_id: UUID,
    payload: ClaimDraft,
) -> ClaimResponse:
    """
    当前用于模拟 Analyst 保存结论。

    后续由 Analyst Agent 自动调用。
    """
    try:
        return claim_service.create_claim(
            task_id=task_id,
            payload=payload,
        )
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (
        ClaimTaskStatusMismatchError,
        InvalidClaimEvidenceReferenceError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[ClaimResponse],
    summary="查询任务全部结论",
)
async def list_claims(
    task_id: UUID,
) -> list[ClaimResponse]:
    """
    查询指定研究任务的全部结论。
    """
    try:
        return claim_service.list_claims_by_task_id(task_id)
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error