from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.agents.planner_agent import PlannerAgent
from app.clients.llm import create_chat_model
from app.repositories.sqlite_agent_run_repository import (
    SQLiteAgentRunRepository,
)
from app.repositories.sqlite_research_plan_repository import (
    SQLiteResearchPlanRepository,
)
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.research_plan import ResearchPlanResponse
from app.services.agent_run_service import AgentRunService
from app.services.planner_execution_service import (
    PlannerExecutionError,
    PlannerExecutionService,
    PlannerTaskStatusMismatchError,
)
from app.services.research_plan_service import ResearchPlanService
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/plan",
    tags=["planner"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

agent_run_repository = SQLiteAgentRunRepository()
agent_run_service = AgentRunService(
    task_repository=task_repository,
    agent_run_repository=agent_run_repository,
)

plan_repository = SQLiteResearchPlanRepository()
research_plan_service = ResearchPlanService(
    task_service=task_service,
    plan_repository=plan_repository,
)

planner_agent = PlannerAgent(llm=create_chat_model())

planner_execution_service = PlannerExecutionService(
    task_service=task_service,
    agent_run_service=agent_run_service,
    research_plan_service=research_plan_service,
    planner_agent=planner_agent,
)


@router.post(
    "/generate",
    response_model=ResearchPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="调用 Planner 自动生成研究计划",
)
async def generate_research_plan(
    task_id: UUID,
) -> ResearchPlanResponse:
    """
    真实调用模型生成研究计划。

    成功后自动保存计划，并将任务状态改为 RESEARCHING。
    """
    try:
        return await planner_execution_service.generate_and_save_plan(
            task_id=task_id,
        )
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except PlannerTaskStatusMismatchError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except PlannerExecutionError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error