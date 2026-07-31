from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.repositories.sqlite_research_plan_repository import (
    SQLiteResearchPlanRepository,
)
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.research_plan import PlannerOutput, ResearchPlanResponse
from app.services.research_plan_service import (
    PlanTaskStatusMismatchError,
    ResearchPlanAlreadyExistsError,
    ResearchPlanNotFoundError,
    ResearchPlanService,
)
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/plan",
    tags=["research-plan"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

plan_repository = SQLiteResearchPlanRepository()
plan_service = ResearchPlanService(
    task_service=task_service,
    plan_repository=plan_repository,
)


@router.post(
    "",
    response_model=ResearchPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="保存研究计划（开发调试）",
)
async def create_research_plan(
    task_id: UUID,
    payload: PlannerOutput,
) -> ResearchPlanResponse:
    """
    当前用于模拟 Planner 的结构化输出。

    后续会由真正的 Planner Agent 自动调用。
    """
    try:
        return plan_service.create_plan(task_id, payload)
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (
        PlanTaskStatusMismatchError,
        ResearchPlanAlreadyExistsError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=ResearchPlanResponse,
    summary="查询研究计划",
)
async def get_research_plan(task_id: UUID) -> ResearchPlanResponse:
    """
    查询任务对应的研究计划和子任务。
    """
    try:
        return plan_service.get_plan_by_task_id(task_id)
    except (TaskNotFoundError, ResearchPlanNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error