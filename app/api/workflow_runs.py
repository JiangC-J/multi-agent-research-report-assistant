from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.repositories.sqlite_task_repository import (
    SQLiteTaskRepository,
)
from app.repositories.sqlite_workflow_run_repository import (
    SQLiteWorkflowRunRepository,
)
from app.schemas.workflow_run import WorkflowRunResponse
from app.services.workflow_run_service import (
    WorkflowRunService,
    WorkflowRunTaskNotFoundError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/workflow-runs",
    tags=["workflow-runs"],
)


workflow_run_service = WorkflowRunService(
    task_repository=SQLiteTaskRepository(),
    workflow_run_repository=(
        SQLiteWorkflowRunRepository()
    ),
)


@router.get(
    "",
    response_model=list[WorkflowRunResponse],
    summary="查询研究任务的工作流执行历史",
)
async def list_workflow_runs(
    task_id: UUID,
) -> list[WorkflowRunResponse]:
    """
    返回指定研究任务的全部后台执行记录。

    结果按 queued_at 倒序排列，
    最新执行记录排在最前面。
    """
    try:
        return workflow_run_service.list_runs_by_task_id(
            task_id
        )
    except WorkflowRunTaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error