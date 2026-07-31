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
from app.schemas.retrieval import MultiQueryRetrievalResponse
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.services.agent_run_service import AgentRunService
from app.services.multi_query_retriever import MultiQueryRetriever
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class RetrievalTaskStatusMismatchError(Exception):
    """
    任务不处于 RESEARCHING 状态时抛出。
    """


class RetrievalSubTaskNotFoundError(Exception):
    """
    子任务不存在或不属于当前任务时抛出。
    """


class RetrievalExecutionError(Exception):
    """
    Query Rewrite 或网页检索执行失败时抛出。
    """


class RetrievalExecutionService:
    """
    单个子任务的多查询检索编排服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        plan_repository: ResearchPlanRepository,
        agent_run_service: AgentRunService,
        query_rewrite_agent: QueryRewriteAgent,
        multi_query_retriever: MultiQueryRetriever,
    ) -> None:
        self._task_service = task_service
        self._plan_repository = plan_repository
        self._agent_run_service = agent_run_service
        self._query_rewrite_agent = query_rewrite_agent
        self._multi_query_retriever = multi_query_retriever

    async def retrieve_for_subtask(
        self,
        task_id: UUID,
        subtask_id: str,
    ) -> MultiQueryRetrievalResponse:
        """
        为一个研究子任务执行 Query Rewrite 与多查询检索。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.RESEARCHING:
            raise RetrievalTaskStatusMismatchError(
                "只有 RESEARCHING 状态的任务可以执行检索；"
                f"当前状态为 {task.status.value}。"
            )

        plan = self._plan_repository.get_by_task_id(task_id)

        if plan is None:
            raise RetrievalSubTaskNotFoundError(
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
            raise RetrievalSubTaskNotFoundError(
                f"{subtask_id} 不属于当前研究计划。"
            )

        agent_run = self._agent_run_service.start_run(
            task_id=task_id,
            payload=AgentRunStart(
                agent_name=AgentName.RESEARCHER,
                input_summary=(
                    f"为子任务 {subtask_id} 生成查询、执行网页检索"
                    "并融合候选资料。"
                ),
            ),
        )

        try:
            query_result = await self._query_rewrite_agent.rewrite_queries(
                subtask=subtask,
                report_language=task.report_language.value,
            )

            documents, failed_queries = (
                await self._multi_query_retriever.retrieve(
                    queries=query_result.query_output.queries,
                )
            )

            if not documents:
                raise RuntimeError("所有检索查询均未返回可用资料。")
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

            raise RetrievalExecutionError(
                "多查询检索失败，请查看任务错误信息和 AgentRun。"
            ) from error

        self._safe_finish_succeeded_run(
            run_id=agent_run.run_id,
            query_count=len(query_result.query_output.queries),
            document_count=len(documents),
            failed_query_count=len(failed_queries),
            input_tokens=query_result.input_tokens,
            output_tokens=query_result.output_tokens,
        )

        return MultiQueryRetrievalResponse(
            query_rewrite_output=query_result.query_output,
            documents=documents,
            failed_queries=failed_queries,
        )

    def _safe_finish_succeeded_run(
        self,
        run_id: UUID,
        query_count: int,
        document_count: int,
        failed_query_count: int,
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
                        f"生成 {query_count} 条查询，融合得到 "
                        f"{document_count} 条候选资料，"
                        f"{failed_query_count} 条查询失败。"
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
        检索失败时将任务标记为 FAILED。
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