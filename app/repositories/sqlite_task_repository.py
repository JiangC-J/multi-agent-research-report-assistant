from uuid import UUID

from app.core.database import SessionLocal
from app.models.research_task import ResearchTaskModel
from app.schemas.research_task import (
    ReportLanguage,
    ResearchTaskResponse,
    TaskStatus,
)


class SQLiteTaskRepository:
    """
    使用 SQLite 持久化研究任务。
    """

    def save(self, task: ResearchTaskResponse) -> ResearchTaskResponse:
        """
        保存任务。

        如果任务不存在则创建；如果已存在则更新。
        """
        with SessionLocal() as session:
            database_task = session.get(
                ResearchTaskModel,
                str(task.task_id),
            )

            if database_task is None:
                database_task = ResearchTaskModel(
                    task_id=str(task.task_id),
                    status=task.status.value,
                    research_topic=task.research_topic,
                    requirements=task.requirements,
                    report_language=task.report_language.value,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    error_message=task.error_message,
                )
                session.add(database_task)
            else:
                database_task.status = task.status.value
                database_task.research_topic = task.research_topic
                database_task.requirements = task.requirements
                database_task.report_language = task.report_language.value
                database_task.updated_at = task.updated_at
                database_task.error_message = task.error_message

            session.commit()

        return task

    def get_by_id(self, task_id: UUID) -> ResearchTaskResponse | None:
        """
        根据任务 ID 查询任务。
        """
        with SessionLocal() as session:
            database_task = session.get(
                ResearchTaskModel,
                str(task_id),
            )

            if database_task is None:
                return None

            return ResearchTaskResponse(
                task_id=UUID(database_task.task_id),
                status=TaskStatus(database_task.status),
                research_topic=database_task.research_topic,
                requirements=database_task.requirements,
                report_language=ReportLanguage(database_task.report_language),
                created_at=database_task.created_at,
                updated_at=database_task.updated_at,
                error_message=database_task.error_message,
            )