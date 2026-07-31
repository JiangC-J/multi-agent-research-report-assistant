from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.agents.query_rewrite_agent import QueryRewriteAgent
from app.clients.llm import create_chat_model
from app.clients.tavily_search import (
    TavilyConfigurationError,
    TavilySearchClient,
)
from app.repositories.sqlite_agent_run_repository import (
    SQLiteAgentRunRepository,
)
from app.repositories.sqlite_research_plan_repository import (
    SQLiteResearchPlanRepository,
)
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.retrieval import MultiQueryRetrievalResponse
from app.services.agent_run_service import AgentRunService
from app.services.multi_query_retriever import MultiQueryRetriever
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)
from app.services.retrieval_execution_service import (
    RetrievalExecutionError,
    RetrievalExecutionService,
    RetrievalSubTaskNotFoundError,
    RetrievalTaskStatusMismatchError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/subtasks/{subtask_id}/retrieval",
    tags=["retrieval"],
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


@router.post(
    "",
    response_model=MultiQueryRetrievalResponse,
    summary="执行多查询检索与 RRF 融合",
)
async def retrieve_for_subtask(
    task_id: UUID,
    subtask_id: str,
) -> MultiQueryRetrievalResponse:
    """
    自动执行 Query Rewrite、并发网页搜索、URL 去重和 RRF 融合。
    """
    try:
        tavily_search_client = TavilySearchClient()

        retrieval_service = RetrievalExecutionService(
            task_service=task_service,
            plan_repository=plan_repository,
            agent_run_service=agent_run_service,
            query_rewrite_agent=query_rewrite_agent,
            multi_query_retriever=MultiQueryRetriever(
                search_client=tavily_search_client,
            ),
        )

        return await retrieval_service.retrieve_for_subtask(
            task_id=task_id,
            subtask_id=subtask_id,
        )
    except (TaskNotFoundError, RetrievalSubTaskNotFoundError) as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except RetrievalTaskStatusMismatchError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except TavilyConfigurationError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
    except RetrievalExecutionError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error