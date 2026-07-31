from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.agents.reviewer_agent import ReviewerAgent
from app.clients.llm import create_chat_model
from app.repositories.sqlite_agent_run_repository import (
    SQLiteAgentRunRepository,
)
from app.repositories.sqlite_claim_repository import SQLiteClaimRepository
from app.repositories.sqlite_evidence_repository import (
    SQLiteEvidenceRepository,
)
from app.repositories.sqlite_review_repository import SQLiteReviewRepository
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.reviewer import ReviewerExecutionResponse
from app.services.agent_run_service import AgentRunService
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)
from app.services.review_service import ReviewService
from app.services.reviewer_execution_service import (
    ReviewerExecutionError,
    ReviewerExecutionService,
    ReviewerTaskStatusMismatchError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/review",
    tags=["reviewer"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

claim_repository = SQLiteClaimRepository()
evidence_repository = SQLiteEvidenceRepository()

review_repository = SQLiteReviewRepository()
review_service = ReviewService(
    task_service=task_service,
    claim_repository=claim_repository,
    review_repository=review_repository,
)

agent_run_repository = SQLiteAgentRunRepository()
agent_run_service = AgentRunService(
    task_repository=task_repository,
    agent_run_repository=agent_run_repository,
)

reviewer_agent = ReviewerAgent(
    llm=create_chat_model(),
)

reviewer_execution_service = ReviewerExecutionService(
    task_service=task_service,
    claim_repository=claim_repository,
    evidence_repository=evidence_repository,
    review_service=review_service,
    agent_run_service=agent_run_service,
    reviewer_agent=reviewer_agent,
)


@router.post(
    "",
    response_model=ReviewerExecutionResponse,
    summary="调用 Reviewer 自动审核结论",
)
async def review_task(
    task_id: UUID,
) -> ReviewerExecutionResponse:
    """
    审核当前任务全部 PENDING Claim。

    本步只更新 Claim 审核结果，
    任务级下一步状态由后续审核汇总策略决定。
    """
    try:
        return await reviewer_execution_service.review_task(
            task_id=task_id,
        )
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ReviewerTaskStatusMismatchError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except ReviewerExecutionError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error