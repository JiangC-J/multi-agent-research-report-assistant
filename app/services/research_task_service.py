from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.repositories.task_repository import TaskRepository
from app.schemas.research_task import (
    ResearchTaskCreate,
    ResearchTaskResponse,
    TaskStatus,
    TaskStatusUpdate,
)


class TaskNotFoundError(Exception):
    """
    查询或更新不存在的任务时抛出。
    """


class InvalidTaskStatusTransitionError(Exception):
    """
    任务状态转换不符合状态机规则时抛出。
    """


ALLOWED_STATUS_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {
        TaskStatus.QUEUED,
        TaskStatus.FAILED,
    },
    TaskStatus.QUEUED: {
        TaskStatus.PLANNING,
        TaskStatus.FAILED,
    },
    TaskStatus.PLANNING: {
        TaskStatus.RESEARCHING,
        TaskStatus.FAILED,
    },
    TaskStatus.RESEARCHING: {
        TaskStatus.ANALYZING,
        TaskStatus.FAILED,
    },
    TaskStatus.ANALYZING: {
        TaskStatus.REVIEWING,
        TaskStatus.FAILED,
    },
    TaskStatus.REVIEWING: {
        TaskStatus.RESEARCHING,
        TaskStatus.WRITING,
        TaskStatus.FAILED,
    },
    TaskStatus.WRITING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
}


class ResearchTaskService:
    """
    研究任务的业务服务。
    """

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    def create_task(self, payload: ResearchTaskCreate) -> ResearchTaskResponse:
        """
        根据用户输入创建一条新的研究任务。
        """
        now = datetime.now(timezone.utc)

        task = ResearchTaskResponse(
            task_id=uuid4(),
            status=TaskStatus.PENDING,
            research_topic=payload.research_topic,
            requirements=payload.requirements,
            report_language=payload.report_language,
            created_at=now,
            updated_at=now,
        )

        return self._repository.save(task)

    def get_task(self, task_id: UUID) -> ResearchTaskResponse | None:
        """
        查询指定研究任务。
        """
        return self._repository.get_by_id(task_id)

    def transition_task_status(
        self,
        task_id: UUID,
        payload: TaskStatusUpdate,
    ) -> ResearchTaskResponse:
        """
        按状态机规则更新任务状态。
        """
        task = self._repository.get_by_id(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        target_status = payload.status

        # 同一状态的重复请求直接返回，保证操作具有幂等性。
        if task.status == target_status:
            return task

        allowed_target_statuses = ALLOWED_STATUS_TRANSITIONS[task.status]

        if target_status not in allowed_target_statuses:
            raise InvalidTaskStatusTransitionError(
                f"不允许将任务状态从 {task.status.value} 转换为 "
                f"{target_status.value}。"
            )

        updated_task = task.model_copy(
            update={
                "status": target_status,
                "updated_at": datetime.now(timezone.utc),
                "error_message": (
                    payload.error_message
                    if target_status == TaskStatus.FAILED
                    else None
                ),
            }
        )

        return self._repository.save(updated_task)