from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.workflow_run import WorkflowRunModel
from app.schemas.workflow_run import (
    WorkflowRunResponse,
    WorkflowRunStatus,
)


class SQLiteWorkflowRunRepository:
    """
    使用 SQLite 持久化完整工作流执行记录。
    """

    def save(
        self,
        workflow_run: WorkflowRunResponse,
    ) -> WorkflowRunResponse:
        """
        保存执行记录。

        run_id 不存在时创建；
        run_id 已存在时更新执行状态和指标。
        """
        with SessionLocal() as session:
            database_run = session.get(
                WorkflowRunModel,
                str(workflow_run.run_id),
            )

            if database_run is None:
                database_run = WorkflowRunModel(
                    run_id=str(workflow_run.run_id),
                    task_id=str(workflow_run.task_id),
                    celery_task_id=workflow_run.celery_task_id,
                    status=workflow_run.status.value,
                    queued_at=workflow_run.queued_at,
                    started_at=workflow_run.started_at,
                    completed_at=workflow_run.completed_at,
                    duration_ms=workflow_run.duration_ms,
                    error_message=workflow_run.error_message,
                )
                session.add(database_run)
            else:
                database_run.status = workflow_run.status.value
                database_run.started_at = workflow_run.started_at
                database_run.completed_at = workflow_run.completed_at
                database_run.duration_ms = workflow_run.duration_ms
                database_run.error_message = (
                    workflow_run.error_message
                )

            session.commit()

        return workflow_run

    def get_by_celery_task_id(
        self,
        celery_task_id: str,
    ) -> WorkflowRunResponse | None:
        """
        根据 Celery Task ID 查询执行记录。
        """
        with SessionLocal() as session:
            statement = select(WorkflowRunModel).where(
                WorkflowRunModel.celery_task_id == celery_task_id
            )

            database_run = session.scalar(statement)

            if database_run is None:
                return None

            return self._to_schema(database_run)

    def list_by_task_id(
        self,
        task_id: UUID,
    ) -> list[WorkflowRunResponse]:
        """
        查询一个研究任务的全部工作流执行记录。

        按入队时间倒序排列，最新一次执行排在最前面。
        """
        with SessionLocal() as session:
            statement = (
                select(WorkflowRunModel)
                .where(
                    WorkflowRunModel.task_id == str(task_id)
                )
                .order_by(
                    WorkflowRunModel.queued_at.desc()
                )
            )

            database_runs = session.scalars(statement).all()

            return [
                self._to_schema(database_run)
                for database_run in database_runs
            ]

    @staticmethod
    def _to_schema(
        database_run: WorkflowRunModel,
    ) -> WorkflowRunResponse:
        """
        将 SQLAlchemy 模型转换为 Pydantic Schema。
        """
        return WorkflowRunResponse(
            run_id=UUID(database_run.run_id),
            task_id=UUID(database_run.task_id),
            celery_task_id=database_run.celery_task_id,
            status=WorkflowRunStatus(database_run.status),
            queued_at=database_run.queued_at,
            started_at=database_run.started_at,
            completed_at=database_run.completed_at,
            duration_ms=database_run.duration_ms,
            error_message=database_run.error_message,
        )