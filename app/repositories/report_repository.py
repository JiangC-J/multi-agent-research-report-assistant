from typing import Protocol
from uuid import UUID

from app.schemas.report import ReportResponse


class ReportRepository(Protocol):
    """
    报告数据访问的抽象约定。
    """

    def create(self, report: ReportResponse) -> ReportResponse:
        """
        保存一份新的报告。
        """

    def get_by_task_id(self, task_id: UUID) -> ReportResponse | None:
        """
        查询任务对应的报告。
        """