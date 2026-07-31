from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.agent_run import (
    AgentName,
    AgentRunFinish,
    AgentRunResponse,
    AgentRunStart,
    AgentRunStatus,
)
from app.schemas.research_task import TaskStatus


class ResearchTaskNotFoundError(Exception):
    """
    Agent 执行所属的研究任务不存在时抛出。
    """


class AgentRunNotFoundError(Exception):
    """
    查询或完成不存在的 AgentRun 时抛出。
    """


class AgentRunTaskStatusMismatchError(Exception):
    """
    Agent 与当前任务状态不匹配时抛出。
    """


class InvalidAgentRunStateError(Exception):
    """
    AgentRun 不处于允许操作状态时抛出。
    """


AGENT_ALLOWED_TASK_STATUSES: dict[AgentName, set[TaskStatus]] = {
    AgentName.PLANNER: {TaskStatus.PLANNING},
    AgentName.RESEARCHER: {TaskStatus.RESEARCHING},
    AgentName.ANALYST: {TaskStatus.ANALYZING},
    AgentName.REVIEWER: {TaskStatus.REVIEWING},
    AgentName.WRITER: {TaskStatus.WRITING},
}


class AgentRunService:
    """
    Agent 执行记录的业务服务。
    """

    def __init__(
        self,
        task_repository: TaskRepository,
        agent_run_repository: AgentRunRepository,
    ) -> None:
        self._task_repository = task_repository
        self._agent_run_repository = agent_run_repository

    def start_run(
        self,
        task_id: UUID,
        payload: AgentRunStart,
    ) -> AgentRunResponse:
        """
        开始一次 Agent 执行并创建 RUNNING 记录。
        """
        task = self._task_repository.get_by_id(task_id)

        if task is None:
            raise ResearchTaskNotFoundError("研究任务不存在。")

        allowed_task_statuses = AGENT_ALLOWED_TASK_STATUSES[payload.agent_name]

        if task.status not in allowed_task_statuses:
            allowed_status_names = ", ".join(
                status.value
                for status in allowed_task_statuses
            )
            raise AgentRunTaskStatusMismatchError(
                f"{payload.agent_name.value} 只能在任务状态为 "
                f"{allowed_status_names} 时执行；当前状态为 "
                f"{task.status.value}。"
            )

        agent_run = AgentRunResponse(
            run_id=uuid4(),
            task_id=task_id,
            agent_name=payload.agent_name,
            status=AgentRunStatus.RUNNING,
            input_summary=payload.input_summary,
            started_at=datetime.now(timezone.utc),
        )

        return self._agent_run_repository.save(agent_run)

    def finish_run(
        self,
        run_id: UUID,
        payload: AgentRunFinish,
    ) -> AgentRunResponse:
        """
        完成一次正在运行的 Agent 执行，并记录指标。
        """
        agent_run = self._agent_run_repository.get_by_id(run_id)

        if agent_run is None:
            raise AgentRunNotFoundError("Agent 执行记录不存在。")

        if agent_run.status != AgentRunStatus.RUNNING:
            raise InvalidAgentRunStateError(
                "只有 RUNNING 状态的 Agent 执行记录可以完成。"
            )

        completed_at = datetime.now(timezone.utc)

# SQLite 不保存 timezone 信息。
# 因此从 SQLite 读取 started_at 时，它通常是“无时区时间”。
# 这里统一将其视为 UTC，再与 completed_at 计算耗时。
        started_at = agent_run.started_at

        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        duration_ms = max(
    int(
        (completed_at - started_at).total_seconds()
        * 1000
    ),
    0,
)

        completed_run = agent_run.model_copy(
            update={
                "status": payload.status,
                "output_summary": payload.output_summary,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "input_tokens": payload.input_tokens,
                "output_tokens": payload.output_tokens,
                "estimated_cost_usd": payload.estimated_cost_usd,
                "error_message": payload.error_message,
            }
        )

        return self._agent_run_repository.save(completed_run)

    def list_runs_by_task_id(
        self,
        task_id: UUID,
    ) -> list[AgentRunResponse]:
        """
        查询指定任务的执行轨迹。
        """
        task = self._task_repository.get_by_id(task_id)

        if task is None:
            raise ResearchTaskNotFoundError("研究任务不存在。")

        return self._agent_run_repository.list_by_task_id(task_id)