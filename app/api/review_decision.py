from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.repositories.sqlite_agent_run_repository import (
    SQLiteAgentRunRepository,
)
from app.repositories.sqlite_claim_repository import SQLiteClaimRepository
from app.repositories.sqlite_review_repository import SQLiteReviewRepository
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.review_decision import TaskReviewDecisionResponse
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)
from app.services.review_aggregation_service import (
    PendingClaimExistsError,
    ReviewAggregationService,
    ReviewAggregationTaskStatusMismatchError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/review",
    tags=["review-decision"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

claim_repository = SQLiteClaimRepository()
review_repository = SQLiteReviewRepository()
agent_run_repository = SQLiteAgentRunRepository()

review_aggregation_service = ReviewAggregationService(
    task_service=task_service,
    claim_repository=claim_repository,
    review_repository=review_repository,
    agent_run_repository=agent_run_repository,
    max_review_iterations=2,
)


@router.post(
    "/decide",
    response_model=TaskReviewDecisionResponse,
    summary="汇总审核结果并决定任务下一步",
)
async def decide_next_step(
    task_id: UUID,
) -> TaskReviewDecisionResponse:
    """
    根据 Claim 审核结果决定：

    - 返回 RESEARCHING 补充研究；
    - 进入 WRITING 生成报告；
    - 标记任务 FAILED。
    """
    try:
        return review_aggregation_service.decide_next_step(
            task_id=task_id,
        )
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except (
        ReviewAggregationTaskStatusMismatchError,
        PendingClaimExistsError,
    ) as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error