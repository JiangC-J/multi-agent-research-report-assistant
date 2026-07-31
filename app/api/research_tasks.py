from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.research_task import (
    ResearchTaskCreate,
    ResearchTaskResponse,
    TaskStatusUpdate,
)
from app.services.research_task_service import (
    InvalidTaskStatusTransitionError,
    ResearchTaskService,
    TaskNotFoundError,
)


router = APIRouter(
    prefix="/research-tasks",
    tags=["research-tasks"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)


@router.post(
    "",
    response_model=ResearchTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建研究任务",
)
async def create_research_task(
    payload: ResearchTaskCreate,
) -> ResearchTaskResponse:
    """
    创建一条新的研究任务。

    新任务的初始状态为 PENDING。
    """
    return task_service.create_task(payload)


@router.get(
    "/{task_id}",
    response_model=ResearchTaskResponse,
    summary="查询研究任务",
)
async def get_research_task(task_id: UUID) -> ResearchTaskResponse:
    """
    根据任务 ID 查询研究任务。
    """
    task = task_service.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="研究任务不存在。",
        )

    return task


@router.patch(
    "/{task_id}/status",
    response_model=ResearchTaskResponse,
    summary="更新任务状态（开发调试）",
)
async def update_research_task_status(
    task_id: UUID,
    payload: TaskStatusUpdate,
) -> ResearchTaskResponse:
    """
    开发阶段用于验证任务状态机。

    后续 Celery Worker 和 LangGraph 会直接调用 Service，
    普通用户不会拥有任意修改状态的权限。
    """
    try:
        return task_service.transition_task_status(task_id, payload)
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except InvalidTaskStatusTransitionError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error