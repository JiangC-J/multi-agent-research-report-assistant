from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.repositories.task_repository import TaskRepository
from app.repositories.workflow_run_repository import (
    WorkflowRunRepository,
)
from app.schemas.workflow_run import (
    WorkflowRunResponse,
    WorkflowRunStatus,
)


class WorkflowRunTaskNotFoundError(Exception):
    """创建执行记录时，所属研究任务不存在。"""


class WorkflowRunNotFoundError(Exception):
    """根据 Celery Task ID 找不到执行记录。"""


class InvalidWorkflowRunStateError(Exception):
    """工作流执行记录状态流转不合法。"""


class WorkflowRunService:
    """
    完整工作流执行记录的业务服务。

    它只管理一次后台执行尝试的状态，
    不负责 Planner、Researcher 等具体业务逻辑。
    """

    def __init__(
        self,
        task_repository: TaskRepository,
        workflow_run_repository: WorkflowRunRepository,
    ) -> None:
        self._task_repository = task_repository
        self._workflow_run_repository = (
            workflow_run_repository
        )

    def create_queued_run(
        self,
        task_id: UUID,
        celery_task_id: str,
    ) -> WorkflowRunResponse:
        """
        API 成功投递 Celery 消息后，创建 QUEUED 执行记录。
        """
        task = self._task_repository.get_by_id(task_id)

        if task is None:
            raise WorkflowRunTaskNotFoundError(
                "研究任务不存在。"
            )

        workflow_run = WorkflowRunResponse(
            run_id=uuid4(),
            task_id=task_id,
            celery_task_id=celery_task_id,
            status=WorkflowRunStatus.QUEUED,
            queued_at=datetime.now(timezone.utc),
        )

        return self._workflow_run_repository.save(
            workflow_run
        )

    def mark_running(
        self,
        celery_task_id: str,
    ) -> WorkflowRunResponse:
        """
        Worker 真正取到消息后，将执行记录推进到 RUNNING。
        """
        workflow_run = self._get_required_run(
            celery_task_id
        )

        if workflow_run.status != WorkflowRunStatus.QUEUED:
            raise InvalidWorkflowRunStateError(
                "只有 QUEUED 状态的工作流执行记录"
                "可以开始运行。"
            )

        running_run = workflow_run.model_copy(
            update={
                "status": WorkflowRunStatus.RUNNING,
                "started_at": datetime.now(timezone.utc),
            }
        )

        return self._workflow_run_repository.save(
            running_run
        )

    def finish_succeeded(
        self,
        celery_task_id: str,
    ) -> WorkflowRunResponse:
        """
        Worker 成功完成工作流后，记录结束时间与实际耗时。
        """
        workflow_run = self._get_required_run(
            celery_task_id
        )

        if workflow_run.status != WorkflowRunStatus.RUNNING:
            raise InvalidWorkflowRunStateError(
                "只有 RUNNING 状态的工作流执行记录"
                "可以标记为成功。"
            )

        completed_at = datetime.now(timezone.utc)

        completed_run = workflow_run.model_copy(
            update={
                "status": WorkflowRunStatus.SUCCEEDED,
                "completed_at": completed_at,
                "duration_ms": self._calculate_duration_ms(
                    workflow_run.started_at,
                    completed_at,
                ),
                "error_message": None,
            }
        )

        return self._workflow_run_repository.save(
            completed_run
        )

    def finish_failed(
        self,
        celery_task_id: str,
        error_message: str,
    ) -> WorkflowRunResponse:
        """
        Worker 失败或超时时，持久化失败状态和错误摘要。
        """
        workflow_run = self._get_required_run(
            celery_task_id
        )

        if workflow_run.status not in {
            WorkflowRunStatus.QUEUED,
            WorkflowRunStatus.RUNNING,
        }:
            raise InvalidWorkflowRunStateError(
                "只有 QUEUED 或 RUNNING 状态的执行记录"
                "可以标记为失败。"
            )

        completed_at = datetime.now(timezone.utc)

        completed_run = workflow_run.model_copy(
            update={
                "status": WorkflowRunStatus.FAILED,
                "completed_at": completed_at,
                "duration_ms": self._calculate_duration_ms(
                    workflow_run.started_at,
                    completed_at,
                ),
                "error_message": error_message[:2000],
            }
        )

        return self._workflow_run_repository.save(
            completed_run
        )

    def list_runs_by_task_id(
        self,
        task_id: UUID,
    ) -> list[WorkflowRunResponse]:
        """
        查询一个研究任务的全部后台执行历史。
        """
        task = self._task_repository.get_by_id(task_id)

        if task is None:
            raise WorkflowRunTaskNotFoundError(
                "研究任务不存在。"
            )

        return self._workflow_run_repository.list_by_task_id(
            task_id
        )

    def _get_required_run(
        self,
        celery_task_id: str,
    ) -> WorkflowRunResponse:
        workflow_run = (
            self._workflow_run_repository
            .get_by_celery_task_id(celery_task_id)
        )

        if workflow_run is None:
            raise WorkflowRunNotFoundError(
                "工作流执行记录不存在。"
            )

        return workflow_run

    @staticmethod
    def _calculate_duration_ms(
        started_at: datetime | None,
        completed_at: datetime,
    ) -> int | None:
        """
        计算 Worker 实际执行耗时。

        若任务在 Worker 启动前就失败，则没有开始时间，
        耗时保留为 null。
        """
        if started_at is None:
            return None

        # SQLite 读出的时间可能不带时区。
        # 统一按 UTC 处理，避免相减报错。
        if started_at.tzinfo is None:
            started_at = started_at.replace(
                tzinfo=timezone.utc,
            )

        return max(
            int(
                (
                    completed_at - started_at
                ).total_seconds()
                * 1000
            ),
            0,
        )