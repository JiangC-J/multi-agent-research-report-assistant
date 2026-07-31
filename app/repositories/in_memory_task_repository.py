from uuid import UUID

from app.schemas.research_task import ResearchTaskResponse


class InMemoryTaskRepository:
    """
    使用 Python 字典临时保存研究任务。

    仅用于开发初期验证 API 和业务流程。
    服务重启后数据会丢失。
    """

    def __init__(self) -> None:
        self._tasks: dict[UUID, ResearchTaskResponse] = {}

    def save(self, task: ResearchTaskResponse) -> ResearchTaskResponse:
        """
        保存一条研究任务。
        """
        self._tasks[task.task_id] = task
        return task

    def get_by_id(self, task_id: UUID) -> ResearchTaskResponse | None:
        """
        根据任务 ID 查询任务。

        如果任务不存在，返回 None。
        """
        return self._tasks.get(task_id)