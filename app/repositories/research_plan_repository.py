from typing import Protocol
from uuid import UUID

from app.schemas.research_plan import ResearchPlanResponse


class ResearchPlanRepository(Protocol):
    """
    研究计划的数据访问约定。
    """

    def save(self, plan: ResearchPlanResponse) -> ResearchPlanResponse:
        """
        保存研究计划及其子任务。
        """

    def get_by_task_id(self, task_id: UUID) -> ResearchPlanResponse | None:
        """
        根据研究任务 ID 查询研究计划。
        """