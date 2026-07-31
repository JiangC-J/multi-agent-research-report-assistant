from uuid import UUID

from app.agents.query_rewrite_agent import QueryRewriteAgent
from app.repositories.research_plan_repository import (
    ResearchPlanRepository,
)
from app.schemas.agent_run import (
    AgentName,
    AgentRunFinish,
    AgentRunStart,
    AgentRunStatus,
)
from app.schemas.research_query import QueryRewriteOutput
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.services.agent_run_service import AgentRunService
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class QueryRewriteTaskStatusMismatchError(Exception):
    """
    任务不处于 RESEARCHING 状态时抛出。
    """


class QueryRewriteSubTaskNotFoundError(Exception):
    """
    子任务不存在或不属于当前任务时抛出。
    """


class QueryRewriteExecutionError(Exception):
    """
    Query Rewrite 模型调用失败时抛出。
    """


class QueryRewriteExecutionService:
    """
    Query Rewrite 的完整执行编排服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        plan_repository: ResearchPlanRepository,
        agent_run_service: AgentRunService,
        query_rewrite_agent: QueryRewriteAgent,
    ) -> None:
        self._task_service = task_service
        self._plan_repository = plan_repository
        self._agent_run_service = agent_run_service
        self._query_rewrite_agent = query_rewrite_agent

    async def generate_queries(
        self,
        task_id: UUID,
        subtask_id: str,
    ) -> QueryRewriteOutput:
        """
        根据指定子任务生成改写查询。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.RESEARCHING:
            raise QueryRewriteTaskStatusMismatchError(
                "只有 RESEARCHING 状态的任务可以执行 Query Rewrite；"
                f"当前状态为 {task.status.value}。"
            )

        plan = self._plan_repository.get_by_task_id(task_id)

        if plan is None:
            raise QueryRewriteSubTaskNotFoundError(
                "当前任务不存在研究计划。"
            )

        subtask = next(
            (
                item
                for item in plan.subtasks
                if item.subtask_id == subtask_id
            ),
            None,
        )

        if subtask is None:
            raise QueryRewriteSubTaskNotFoundError(
                f"{subtask_id} 不属于当前研究计划。"
            )

        agent_run = self._agent_run_service.start_run(
            task_id=task_id,
            payload=AgentRunStart(
                agent_name=AgentName.RESEARCHER,
                input_summary=(
                    f"为子任务 {subtask_id} 生成多查询检索计划。"
                ),
            ),
        )

        try:
            agent_result = await self._query_rewrite_agent.rewrite_queries(
                subtask=subtask,
                report_language=task.report_language.value,
            )
        except Exception as error:
            error_message = str(error)[:2000]

            self._safe_finish_failed_run(
                run_id=agent_run.run_id,
                error_message=error_message,
            )
            self._safe_mark_task_failed(
                task_id=task_id,
                error_message=error_message,
            )

            raise QueryRewriteExecutionError(
                "Query Rewrite 执行失败，请查看任务错误信息和 AgentRun。"
            ) from error

        self._safe_finish_succeeded_run(
            run_id=agent_run.run_id,
            query_count=len(agent_result.query_output.queries),
            input_tokens=agent_result.input_tokens,
            output_tokens=agent_result.output_tokens,
        )

        return agent_result.query_output

    def _safe_finish_succeeded_run(
        self,
        run_id: UUID,
        query_count: int,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        尽力记录成功执行指标。
        """
        try:
            self._agent_run_service.finish_run(
                run_id=run_id,
                payload=AgentRunFinish(
                    status=AgentRunStatus.SUCCEEDED,
                    output_summary=(
                        f"成功生成 {query_count} 条改写检索查询。"
                    ),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=0.0,
                ),
            )
        except Exception:
            pass

    def _safe_finish_failed_run(
        self,
        run_id: UUID,
        error_message: str,
    ) -> None:
        """
        尽力记录失败执行信息。
        """
        try:
            self._agent_run_service.finish_run(
                run_id=run_id,
                payload=AgentRunFinish(
                    status=AgentRunStatus.FAILED,
                    error_message=error_message,
                ),
            )
        except Exception:
            pass

    def _safe_mark_task_failed(
        self,
        task_id: UUID,
        error_message: str,
    ) -> None:
        """
        Query Rewrite 失败时，将任务标记为 FAILED。
        """
        try:
            task = self._task_service.get_task(task_id)

            if task is not None and task.status == TaskStatus.RESEARCHING:
                self._task_service.transition_task_status(
                    task_id=task_id,
                    payload=TaskStatusUpdate(
                        status=TaskStatus.FAILED,
                        error_message=error_message,
                    ),
                )
        except Exception:
            pass