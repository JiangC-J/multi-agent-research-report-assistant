from typing import Protocol
from uuid import UUID

from app.schemas.research_task import ResearchTaskResponse


class TaskRepository(Protocol):
    """
    研究任务数据访问的抽象约定。
    """

    def save(self, task: ResearchTaskResponse) -> ResearchTaskResponse:
        """
        保存一条研究任务。
        """

    def get_by_id(self, task_id: UUID) -> ResearchTaskResponse | None:
        """
        根据任务 ID 查询研究任务。
        """