import asyncio
from typing import Any
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.graphs.factory import create_research_workflow
from app.repositories.sqlite_task_repository import (
    SQLiteTaskRepository,
)
from app.repositories.sqlite_workflow_run_repository import (
    SQLiteWorkflowRunRepository,
)
from app.schemas.research_task import (
    TaskStatus,
    TaskStatusUpdate,
)
from app.services.research_task_service import (
    InvalidTaskStatusTransitionError,
    ResearchTaskService,
)
from app.services.workflow_run_service import (
    WorkflowRunService,
)


task_repository = SQLiteTaskRepository()

task_service = ResearchTaskService(
    repository=task_repository,
)

workflow_run_service = WorkflowRunService(
    task_repository=task_repository,
    workflow_run_repository=(
        SQLiteWorkflowRunRepository()
    ),
)


async def _run_langgraph_workflow(
    task_id: UUID,
) -> dict[str, Any]:
    """
    在 Celery Worker 内部运行异步 LangGraph 工作流。
    """
    workflow = create_research_workflow()

    initial_state = {
        "task_id": str(task_id),
        "workflow_status": "created",
        "subtask_ids": [],
        "current_subtask_index": 0,
        "completed_subtask_ids": [],
        "execution_log": [],
        "review_outcome": None,
        "required_actions": [],
        "report_id": None,
        "error_message": None,
    }

    result = await workflow.ainvoke(
        initial_state,
        config={
            "recursion_limit": 30,
        },
    )

    return {
        "task_id": str(task_id),
        "workflow_status": result["workflow_status"],
        "completed_subtask_ids": result.get(
            "completed_subtask_ids",
            [],
        ),
        "review_outcome": result.get("review_outcome"),
        "required_actions": result.get(
            "required_actions",
            [],
        ),
        "report_id": result.get("report_id"),
        "error_message": result.get("error_message"),
    }


def _safe_mark_task_failed(
    task_id: UUID,
    error_message: str,
) -> None:
    """
    尽力把业务任务标记为 FAILED。

    记录失败本身不能覆盖原始异常。
    """
    try:
        task = task_service.get_task(task_id)

        if task is None:
            return

        if task.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
        }:
            return

        task_service.transition_task_status(
            task_id=task_id,
            payload=TaskStatusUpdate(
                status=TaskStatus.FAILED,
                error_message=error_message[:2000],
            ),
        )
    except (
        InvalidTaskStatusTransitionError,
        Exception,
    ):
        return


def _safe_finish_workflow_run_failed(
    celery_task_id: str,
    error_message: str,
) -> None:
    """
    尽力将 WorkflowRun 标记为 FAILED。
    """
    try:
        workflow_run_service.finish_failed(
            celery_task_id=celery_task_id,
            error_message=error_message[:2000],
        )
    except Exception:
        return


@celery_app.task(
    bind=True,
    name="research_agent.run_research_workflow",
)
def run_research_workflow_task(
    self,
    task_id: str,
) -> dict[str, Any]:
    """
    执行完整多 Agent 研究工作流。

    bind=True 让任务能通过 self.request.id
    获得当前真实的 Celery Task ID。
    """
    celery_task_id = self.request.id
    parsed_task_id = UUID(task_id)

    try:
        # Worker 真正消费消息时，执行记录进入 RUNNING。
        workflow_run_service.mark_running(
            celery_task_id
        )

        task = task_service.get_task(parsed_task_id)

        if task is None:
            raise ValueError(
                f"研究任务不存在：{task_id}"
            )

        if task.status != TaskStatus.QUEUED:
            raise ValueError(
                "Worker 只执行 QUEUED 状态的任务，"
                f"当前状态为 {task.status.value}。"
            )

        result = asyncio.run(
            _run_langgraph_workflow(
                task_id=parsed_task_id,
            )
        )

        workflow_run_service.finish_succeeded(
            celery_task_id
        )

        return result

    except SoftTimeLimitExceeded as error:
        error_message = "工作流超过 Celery 软超时限制。"

        _safe_finish_workflow_run_failed(
            celery_task_id=celery_task_id,
            error_message=error_message,
        )

        _safe_mark_task_failed(
            task_id=parsed_task_id,
            error_message=error_message,
        )

        raise RuntimeError(error_message) from error

    except Exception as error:
        error_message = (
            f"后台工作流执行失败：{str(error)}"
        )

        _safe_finish_workflow_run_failed(
            celery_task_id=celery_task_id,
            error_message=error_message,
        )

        _safe_mark_task_failed(
            task_id=parsed_task_id,
            error_message=error_message,
        )

        raise