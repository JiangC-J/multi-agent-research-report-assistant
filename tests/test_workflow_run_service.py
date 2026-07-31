from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.schemas.workflow_run import WorkflowRunStatus
from app.services.workflow_run_service import (
    InvalidWorkflowRunStateError,
    WorkflowRunService,
)


TASK_ID = UUID(
    "11111111-1111-1111-1111-111111111111"
)


class FakeTaskRepository:
    """最小任务仓库替身。"""

    def get_by_id(self, task_id):
        if task_id == TASK_ID:
            return SimpleNamespace(task_id=TASK_ID)

        return None


class FakeWorkflowRunRepository:
    """使用内存字典模拟工作流执行记录仓库。"""

    def __init__(self) -> None:
        self.runs_by_celery_task_id = {}

    def save(self, workflow_run):
        self.runs_by_celery_task_id[
            workflow_run.celery_task_id
        ] = workflow_run

        return workflow_run

    def get_by_celery_task_id(
        self,
        celery_task_id: str,
    ):
        return self.runs_by_celery_task_id.get(
            celery_task_id
        )

    def list_by_task_id(self, task_id):
        return [
            workflow_run
            for workflow_run in (
                self.runs_by_celery_task_id.values()
            )
            if workflow_run.task_id == task_id
        ]


def build_service():
    """
    创建不依赖真实 SQLite 的 WorkflowRunService。
    """
    return WorkflowRunService(
        task_repository=FakeTaskRepository(),
        workflow_run_repository=(
            FakeWorkflowRunRepository()
        ),
    )


def test_workflow_run_moves_from_queued_to_succeeded():
    """
    正常执行应遵循：
    QUEUED → RUNNING → SUCCEEDED。
    """
    service = build_service()
    celery_task_id = str(uuid4())

    queued_run = service.create_queued_run(
        task_id=TASK_ID,
        celery_task_id=celery_task_id,
    )

    running_run = service.mark_running(
        celery_task_id
    )

    succeeded_run = service.finish_succeeded(
        celery_task_id
    )

    assert queued_run.status == WorkflowRunStatus.QUEUED
    assert running_run.status == WorkflowRunStatus.RUNNING
    assert running_run.started_at is not None
    assert succeeded_run.status == WorkflowRunStatus.SUCCEEDED
    assert succeeded_run.completed_at is not None
    assert succeeded_run.duration_ms is not None
    assert succeeded_run.error_message is None


def test_queued_run_can_be_marked_failed():
    """
    Worker 启动前失败时，执行记录允许：
    QUEUED → FAILED。
    """
    service = build_service()
    celery_task_id = str(uuid4())

    service.create_queued_run(
        task_id=TASK_ID,
        celery_task_id=celery_task_id,
    )

    failed_run = service.finish_failed(
        celery_task_id=celery_task_id,
        error_message="Redis Broker 不可用。",
    )

    assert failed_run.status == WorkflowRunStatus.FAILED
    assert failed_run.started_at is None
    assert failed_run.duration_ms is None
    assert failed_run.error_message == "Redis Broker 不可用。"


def test_cannot_finish_queued_run_as_succeeded():
    """
    未进入 RUNNING 的任务不能直接成功，
    防止出现伪造的执行时间和状态。
    """
    service = build_service()
    celery_task_id = str(uuid4())

    service.create_queued_run(
        task_id=TASK_ID,
        celery_task_id=celery_task_id,
    )

    with pytest.raises(
        InvalidWorkflowRunStateError
    ):
        service.finish_succeeded(celery_task_id)