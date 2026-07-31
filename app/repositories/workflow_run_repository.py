from typing import Protocol
from uuid import UUID

from app.schemas.workflow_run import WorkflowRunResponse


class WorkflowRunRepository(Protocol):
    """
    工作流执行记录的数据访问约定。

    Service 只依赖这个接口，
    不直接依赖 SQLite 的具体实现。
    """

    def save(
        self,
        workflow_run: WorkflowRunResponse,
    ) -> WorkflowRunResponse:
        """创建或更新一条工作流执行记录。"""

    def get_by_celery_task_id(
        self,
        celery_task_id: str,
    ) -> WorkflowRunResponse | None:
        """根据 Celery Task ID 查询执行记录。"""

    def list_by_task_id(
        self,
        task_id: UUID,
    ) -> list[WorkflowRunResponse]:
        """查询一个研究任务的全部执行历史。"""