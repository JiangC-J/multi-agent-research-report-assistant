from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status

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
from app.schemas.workflow import WorkflowTaskAcceptedResponse
from app.services.research_task_service import (
    InvalidTaskStatusTransitionError,
    ResearchTaskService,
)
from app.services.workflow_run_service import (
    WorkflowRunService,
)
from app.tasks.research_workflow import run_research_workflow_task


router = APIRouter(
    prefix="/research-tasks/{task_id}/run",
    tags=["workflow"],
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


@router.post(
    "",
    response_model=WorkflowTaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="投递多 Agent 研究工作流到后台队列",
)
async def run_research_workflow(
    task_id: UUID,
) -> WorkflowTaskAcceptedResponse:
    """
    将研究工作流投递给 Celery Worker。

    API 只负责：
    1. 验证任务；
    2. 将业务任务标记为 QUEUED；
    3. 创建 WorkflowRun；
    4. 发布 Celery 消息。

    不等待 LangGraph 完成。
    """
    task = task_service.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="研究任务不存在。",
        )

    if task.status != TaskStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "只有 PENDING 状态的研究任务可以投递执行，"
                f"当前状态为 {task.status.value}。"
            ),
        )

    # 先生成任务 ID，再用同一个 ID：
    # 1. 作为 Celery 消息 ID；
    # 2. 写入 SQLite WorkflowRun。
    # 这样两套系统可通过 celery_task_id 关联。
    celery_task_id = str(uuid4())
    workflow_run = None

    try:
        queued_task = task_service.transition_task_status(
            task_id=task_id,
            payload=TaskStatusUpdate(
                status=TaskStatus.QUEUED,
            ),
        )

        workflow_run = workflow_run_service.create_queued_run(
            task_id=task_id,
            celery_task_id=celery_task_id,
        )

        run_research_workflow_task.apply_async(
            args=[str(task_id)],
            task_id=celery_task_id,
        )

    except InvalidTaskStatusTransitionError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    except Exception as error:
        error_message = (
            "任务投递到后台队列失败："
            f"{str(error)}"
        )[:2000]

        # 若 WorkflowRun 已创建，则同步写入失败审计。
        if workflow_run is not None:
            try:
                workflow_run_service.finish_failed(
                    celery_task_id=celery_task_id,
                    error_message=error_message,
                )
            except Exception:
                pass

        # 同时把业务任务从 QUEUED 置为 FAILED。
        try:
            task_service.transition_task_status(
                task_id=task_id,
                payload=TaskStatusUpdate(
                    status=TaskStatus.FAILED,
                    error_message=error_message,
                ),
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "后台任务队列暂时不可用，"
                "请检查 Redis 和 Celery Worker。"
            ),
        ) from error

    return WorkflowTaskAcceptedResponse(
        task_id=task_id,
        celery_task_id=celery_task_id,
        workflow_run_id=workflow_run.run_id,
        task_status=queued_task.status,
        celery_state="PENDING",
        message=(
            "研究任务已进入后台队列。"
            "请通过研究任务状态、工作流执行记录"
            "或 Celery 技术状态接口查询进度。"
        ),
    )