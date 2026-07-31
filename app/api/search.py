from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.clients.tavily_search import (
    TavilyConfigurationError,
    TavilySearchClient,
)
from app.repositories.sqlite_research_plan_repository import (
    SQLiteResearchPlanRepository,
)
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.search import SearchRequest, SearchResponse
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)
from app.services.search_service import (
    SearchService,
    SearchSubTaskNotFoundError,
    SearchTaskStatusMismatchError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/subtasks/{subtask_id}/search",
    tags=["search"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

plan_repository = SQLiteResearchPlanRepository()


@router.post(
    "",
    response_model=SearchResponse,
    summary="执行网页搜索（开发调试）",
)
async def search_subtask(
    task_id: UUID,
    subtask_id: str,
    payload: SearchRequest,
) -> SearchResponse:
    """
    使用 Tavily 搜索指定子任务相关资料。
    """
    try:
        search_client = TavilySearchClient()

        search_service = SearchService(
            task_service=task_service,
            plan_repository=plan_repository,
            search_client=search_client,
        )

        return await search_service.search_subtask(
            task_id=task_id,
            subtask_id=subtask_id,
            payload=payload,
        )
    except (TaskNotFoundError, SearchSubTaskNotFoundError) as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except SearchTaskStatusMismatchError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except TavilyConfigurationError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error