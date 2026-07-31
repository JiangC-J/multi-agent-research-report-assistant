from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.repositories.sqlite_claim_repository import SQLiteClaimRepository
from app.repositories.sqlite_review_repository import SQLiteReviewRepository
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.review import ClaimReviewDraft, ClaimReviewResponse
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)
from app.services.review_service import (
    ClaimAlreadyReviewedError,
    ClaimNotFoundError,
    InvalidReviewEvidenceReferenceError,
    ReviewService,
    ReviewTaskStatusMismatchError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/claims/{claim_id}/reviews",
    tags=["reviews"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

claim_repository = SQLiteClaimRepository()
review_repository = SQLiteReviewRepository()

review_service = ReviewService(
    task_service=task_service,
    claim_repository=claim_repository,
    review_repository=review_repository,
)


@router.post(
    "",
    response_model=ClaimReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="审核结论（开发调试）",
)
async def create_review(
    task_id: UUID,
    claim_id: UUID,
    payload: ClaimReviewDraft,
) -> ClaimReviewResponse:
    """
    当前用于模拟 Reviewer 审核结论。

    后续由 Reviewer Agent 自动调用。
    """
    try:
        return review_service.create_review(
            task_id=task_id,
            claim_id=claim_id,
            payload=payload,
        )
    except (TaskNotFoundError, ClaimNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (
        ReviewTaskStatusMismatchError,
        ClaimAlreadyReviewedError,
        InvalidReviewEvidenceReferenceError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[ClaimReviewResponse],
    summary="查询结论审核历史",
)
async def list_reviews(
    task_id: UUID,
    claim_id: UUID,
) -> list[ClaimReviewResponse]:
    """
    查询指定 Claim 的全部审核记录。
    """
    try:
        return review_service.list_reviews_by_claim_id(
            task_id=task_id,
            claim_id=claim_id,
        )
    except (TaskNotFoundError, ClaimNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error