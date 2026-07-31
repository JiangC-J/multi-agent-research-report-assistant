from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.repositories.sqlite_agent_run_repository import (
    SQLiteAgentRunRepository,
)
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.agent_run import (
    AgentRunFinish,
    AgentRunResponse,
    AgentRunStart,
)
from app.services.agent_run_service import (
    AgentRunNotFoundError,
    AgentRunService,
    AgentRunTaskStatusMismatchError,
    InvalidAgentRunStateError,
    ResearchTaskNotFoundError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/agent-runs",
    tags=["agent-runs"],
)

task_repository = SQLiteTaskRepository()
agent_run_repository = SQLiteAgentRunRepository()

agent_run_service = AgentRunService(
    task_repository=task_repository,
    agent_run_repository=agent_run_repository,
)


@router.post(
    "",
    response_model=AgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="开始 Agent 执行（开发调试）",
)
async def start_agent_run(
    task_id: UUID,
    payload: AgentRunStart,
) -> AgentRunResponse:
    """
    创建一条 RUNNING 状态的 Agent 执行记录。

    当前仅用于开发验证。
    后续由 LangGraph 节点在内部调用。
    """
    try:
        return agent_run_service.start_run(task_id, payload)
    except ResearchTaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except AgentRunTaskStatusMismatchError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.patch(
    "/{run_id}",
    response_model=AgentRunResponse,
    summary="完成 Agent 执行（开发调试）",
)
async def finish_agent_run(
    task_id: UUID,
    run_id: UUID,
    payload: AgentRunFinish,
) -> AgentRunResponse:
    """
    将 RUNNING 状态的执行记录更新为 SUCCEEDED 或 FAILED。
    """
    try:
        agent_run = agent_run_service.finish_run(run_id, payload)

        if agent_run.task_id != task_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="该 Agent 执行记录不属于当前研究任务。",
            )

        return agent_run
    except AgentRunNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except InvalidAgentRunStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[AgentRunResponse],
    summary="查询任务执行轨迹",
)
async def list_agent_runs(task_id: UUID) -> list[AgentRunResponse]:
    """
    查询一个研究任务的全部 Agent 执行记录。
    """
    try:
        return agent_run_service.list_runs_by_task_id(task_id)
    except ResearchTaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error