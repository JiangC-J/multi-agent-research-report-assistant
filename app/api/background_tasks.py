from celery import states
from fastapi import APIRouter

from app.core.celery_app import celery_app
from app.schemas.background_task import (
    BackgroundTaskStatusResponse,
)


router = APIRouter(
    prefix="/background-tasks",
    tags=["background-tasks"],
)


@router.get(
    "/{celery_task_id}",
    response_model=BackgroundTaskStatusResponse,
    summary="查询 Celery 后台任务技术状态",
)
async def get_background_task_status(
    celery_task_id: str,
) -> BackgroundTaskStatusResponse:
    """
    查询 Redis Result Backend 中记录的 Celery 任务状态。

    这个接口只查看后台任务技术状态，
    不影响研究任务、不会重新执行工作流。
    """
    async_result = celery_app.AsyncResult(
        celery_task_id,
    )

    celery_state = async_result.state

    if celery_state == states.SUCCESS:
        task_result = async_result.result

        return BackgroundTaskStatusResponse(
            celery_task_id=celery_task_id,
            celery_state=celery_state,
            is_ready=True,
            is_successful=True,
            result=(
                task_result
                if isinstance(task_result, dict)
                else {"value": str(task_result)}
            ),
        )

    if celery_state == states.FAILURE:
        return BackgroundTaskStatusResponse(
            celery_task_id=celery_task_id,
            celery_state=celery_state,
            is_ready=True,
            is_successful=False,
            error_message=str(async_result.result)[:2000],
        )

    return BackgroundTaskStatusResponse(
        celery_task_id=celery_task_id,
        celery_state=celery_state,
        is_ready=False,
        is_successful=None,
    )