from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.agents.query_rewrite_agent import QueryRewriteAgent
from app.clients.llm import create_chat_model
from app.repositories.sqlite_agent_run_repository import (
    SQLiteAgentRunRepository,
)
from app.repositories.sqlite_research_plan_repository import (
    SQLiteResearchPlanRepository,
)
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.research_query import QueryRewriteOutput
from app.services.agent_run_service import AgentRunService
from app.services.query_rewrite_execution_service import (
    QueryRewriteExecutionError,
    QueryRewriteExecutionService,
    QueryRewriteSubTaskNotFoundError,
    QueryRewriteTaskStatusMismatchError,
)
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/subtasks/{subtask_id}/queries",
    tags=["query-rewrite"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

plan_repository = SQLiteResearchPlanRepository()

agent_run_repository = SQLiteAgentRunRepository()
agent_run_service = AgentRunService(
    task_repository=task_repository,
    agent_run_repository=agent_run_repository,
)

query_rewrite_agent = QueryRewriteAgent(
    llm=create_chat_model(),
)

query_rewrite_execution_service = QueryRewriteExecutionService(
    task_service=task_service,
    plan_repository=plan_repository,
    agent_run_service=agent_run_service,
    query_rewrite_agent=query_rewrite_agent,
)


@router.post(
    "/generate",
    response_model=QueryRewriteOutput,
    summary="调用 Researcher 生成改写查询",
)
async def generate_rewritten_queries(
    task_id: UUID,
    subtask_id: str,
) -> QueryRewriteOutput:
    """
    真实调用模型，为指定研究子任务生成改写查询。
    """
    try:
        return await query_rewrite_execution_service.generate_queries(
            task_id=task_id,
            subtask_id=subtask_id,
        )
    except (TaskNotFoundError, QueryRewriteSubTaskNotFoundError) as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except QueryRewriteTaskStatusMismatchError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except QueryRewriteExecutionError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error