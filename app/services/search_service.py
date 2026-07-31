from uuid import UUID

from app.clients.tavily_search import TavilySearchClient
from app.repositories.research_plan_repository import (
    ResearchPlanRepository,
)
from app.schemas.search import SearchRequest, SearchResponse
from app.schemas.research_task import TaskStatus
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class SearchTaskStatusMismatchError(Exception):
    """
    任务不处于 RESEARCHING 状态时抛出。
    """


class SearchSubTaskNotFoundError(Exception):
    """
    子任务不存在或不属于当前任务时抛出。
    """


class SearchService:
    """
    Researcher 使用的网页搜索服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        plan_repository: ResearchPlanRepository,
        search_client: TavilySearchClient,
    ) -> None:
        self._task_service = task_service
        self._plan_repository = plan_repository
        self._search_client = search_client

    async def search_subtask(
        self,
        task_id: UUID,
        subtask_id: str,
        payload: SearchRequest,
    ) -> SearchResponse:
        """
        在合法的 RESEARCHING 阶段执行一次网页搜索。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.RESEARCHING:
            raise SearchTaskStatusMismatchError(
                "只有 RESEARCHING 状态的任务可以执行网页搜索；"
                f"当前状态为 {task.status.value}。"
            )

        plan = self._plan_repository.get_by_task_id(task_id)

        if plan is None:
            raise SearchSubTaskNotFoundError(
                "当前任务不存在研究计划。"
            )

        is_valid_subtask = any(
            subtask.subtask_id == subtask_id
            for subtask in plan.subtasks
        )

        if not is_valid_subtask:
            raise SearchSubTaskNotFoundError(
                f"{subtask_id} 不属于当前研究计划。"
            )

        return await self._search_client.search(
            query=payload.query,
            max_results=payload.max_results,
        )