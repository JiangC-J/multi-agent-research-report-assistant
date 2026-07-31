from uuid import UUID

from app.agents.planner_agent import PlannerAgent
from app.schemas.agent_run import (
    AgentName,
    AgentRunFinish,
    AgentRunStart,
    AgentRunStatus,
)
from app.schemas.research_plan import ResearchPlanResponse
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.services.agent_run_service import AgentRunService
from app.services.research_plan_service import ResearchPlanService
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class PlannerTaskStatusMismatchError(Exception):
    """
    任务不处于 PLANNING 状态时抛出。
    """


class PlannerExecutionError(Exception):
    """
    Planner 调用模型或保存计划失败时抛出。
    """


class PlannerExecutionService:
    """
    Planner 的完整执行编排服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        agent_run_service: AgentRunService,
        research_plan_service: ResearchPlanService,
        planner_agent: PlannerAgent,
    ) -> None:
        self._task_service = task_service
        self._agent_run_service = agent_run_service
        self._research_plan_service = research_plan_service
        self._planner_agent = planner_agent

    async def generate_and_save_plan(
        self,
        task_id: UUID,
    ) -> ResearchPlanResponse:
        """
        执行 Planner，保存计划，并推动任务进入 RESEARCHING。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.PLANNING:
            raise PlannerTaskStatusMismatchError(
                "只有 PLANNING 状态的任务可以执行 Planner；"
                f"当前状态为 {task.status.value}。"
            )

        agent_run = self._agent_run_service.start_run(
            task_id=task_id,
            payload=AgentRunStart(
                agent_name=AgentName.PLANNER,
                input_summary=(
                    "根据用户研究主题和补充要求生成结构化研究计划。"
                ),
            ),
        )

        try:
            agent_result = await self._planner_agent.create_plan(
                research_topic=task.research_topic,
                requirements=task.requirements,
                report_language=task.report_language.value,
            )

            saved_plan = self._research_plan_service.create_plan(
                task_id=task_id,
                payload=agent_result.plan,
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

            raise PlannerExecutionError(
                f"Planner 执行失败：{error_message}"
            ) from error

        self._safe_finish_succeeded_run(
            run_id=agent_run.run_id,
            plan_title=agent_result.plan.plan_title,
            subtask_count=len(agent_result.plan.subtasks),
            input_tokens=agent_result.input_tokens,
            output_tokens=agent_result.output_tokens,
        )

        return saved_plan

    def _safe_finish_succeeded_run(
        self,
        run_id: UUID,
        plan_title: str,
        subtask_count: int,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        尽力记录成功执行指标。

        计划已成功保存后，即使记录指标异常，也不应回滚业务结果。
        """
        try:
            self._agent_run_service.finish_run(
                run_id=run_id,
                payload=AgentRunFinish(
                    status=AgentRunStatus.SUCCEEDED,
                    output_summary=(
                        f"成功生成研究计划《{plan_title}》，"
                        f"包含 {subtask_count} 个子任务。"
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
        Planner 失败时，将仍处于 PLANNING 的任务标记为 FAILED。
        """
        try:
            task = self._task_service.get_task(task_id)

            if task is not None and task.status == TaskStatus.PLANNING:
                self._task_service.transition_task_status(
                    task_id=task_id,
                    payload=TaskStatusUpdate(
                        status=TaskStatus.FAILED,
                        error_message=error_message,
                    ),
                )
        except Exception:
            pass
