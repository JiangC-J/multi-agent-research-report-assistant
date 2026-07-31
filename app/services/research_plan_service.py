from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.repositories.research_plan_repository import (
    ResearchPlanRepository,
)
from app.schemas.research_plan import PlannerOutput, ResearchPlanResponse
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class ResearchPlanAlreadyExistsError(Exception):
    """
    当前任务已有研究计划时抛出。
    """


class PlanTaskStatusMismatchError(Exception):
    """
    任务不在 PLANNING 状态时抛出。
    """


class ResearchPlanNotFoundError(Exception):
    """
    查询不到研究计划时抛出。
    """


class ResearchPlanService:
    """
    研究计划的业务服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        plan_repository: ResearchPlanRepository,
    ) -> None:
        self._task_service = task_service
        self._plan_repository = plan_repository

    def create_plan(
        self,
        task_id: UUID,
        payload: PlannerOutput,
    ) -> ResearchPlanResponse:
        """
        保存 Planner 输出的研究计划。

        保存成功后，任务状态自动从 PLANNING 进入 RESEARCHING。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.PLANNING:
            raise PlanTaskStatusMismatchError(
                "只有 PLANNING 状态的任务可以保存研究计划；"
                f"当前状态为 {task.status.value}。"
            )

        existing_plan = self._plan_repository.get_by_task_id(task_id)

        if existing_plan is not None:
            raise ResearchPlanAlreadyExistsError(
                "当前研究任务已经存在研究计划。"
            )

        plan = ResearchPlanResponse(
            plan_id=uuid4(),
            task_id=task_id,
            plan_title=payload.plan_title,
            overall_strategy=payload.overall_strategy,
            subtasks=payload.subtasks,
            created_at=datetime.now(timezone.utc),
        )

        saved_plan = self._plan_repository.save(plan)

        self._task_service.transition_task_status(
            task_id=task_id,
            payload=TaskStatusUpdate(
                status=TaskStatus.RESEARCHING,
            ),
        )

        return saved_plan

    def get_plan_by_task_id(self, task_id: UUID) -> ResearchPlanResponse:
        """
        查询指定任务的研究计划。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        plan = self._plan_repository.get_by_task_id(task_id)

        if plan is None:
            raise ResearchPlanNotFoundError("研究计划不存在。")

        return plan