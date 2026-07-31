from uuid import UUID

from app.agents.analyst_agent import AnalystAgent
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.agent_run import (
    AgentName,
    AgentRunFinish,
    AgentRunStart,
    AgentRunStatus,
)
from app.schemas.analyst import AnalystExecutionResponse
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.services.agent_run_service import AgentRunService
from app.services.claim_service import ClaimService
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class AnalystTaskStatusMismatchError(Exception):
    """
    任务不处于 ANALYZING 状态时抛出。
    """


class AnalystExecutionError(Exception):
    """
    Analyst 执行失败时抛出。
    """


class AnalystExecutionService:
    """
    Analyst 的完整执行编排服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        evidence_repository: EvidenceRepository,
        claim_service: ClaimService,
        agent_run_service: AgentRunService,
        analyst_agent: AnalystAgent,
    ) -> None:
        self._task_service = task_service
        self._evidence_repository = evidence_repository
        self._claim_service = claim_service
        self._agent_run_service = agent_run_service
        self._analyst_agent = analyst_agent

    async def analyze_task(
        self,
        task_id: UUID,
    ) -> AnalystExecutionResponse:
        """
        基于任务 Evidence 生成 Claim，并推进任务进入 REVIEWING。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.ANALYZING:
            raise AnalystTaskStatusMismatchError(
                "只有 ANALYZING 状态的任务可以执行 Analyst；"
                f"当前状态为 {task.status.value}。"
            )

        evidences = self._evidence_repository.list_by_task_id(task_id)

        if not evidences:
            raise AnalystExecutionError(
                "当前任务没有可用于分析的 Evidence。"
            )

        # 第一版限制输入数量，避免单次模型上下文过长。
        selected_evidences = evidences[:12]

        agent_run = self._agent_run_service.start_run(
            task_id=task_id,
            payload=AgentRunStart(
                agent_name=AgentName.ANALYST,
                input_summary=(
                    f"基于 {len(selected_evidences)} 条 Evidence "
                    "生成结构化 Claim。"
                ),
            ),
        )

        try:
            agent_result = await self._analyst_agent.analyze(
                research_topic=task.research_topic,
                requirements=task.requirements,
                evidences=selected_evidences,
            )

            saved_claims = [
                self._claim_service.create_claim(
                    task_id=task_id,
                    payload=claim_draft,
                )
                for claim_draft in agent_result.analysis_output.claims
            ]

            self._task_service.transition_task_status(
                task_id=task_id,
                payload=TaskStatusUpdate(
                    status=TaskStatus.REVIEWING,
                ),
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

            raise AnalystExecutionError(
                f"Analyst 执行失败：{error_message}"
            ) from error

        self._safe_finish_succeeded_run(
            run_id=agent_run.run_id,
            claim_count=len(saved_claims),
            input_tokens=agent_result.input_tokens,
            output_tokens=agent_result.output_tokens,
        )

        return AnalystExecutionResponse(
            input_evidence_count=len(selected_evidences),
            saved_claims=saved_claims,
        )

    def _safe_finish_succeeded_run(
        self,
        run_id: UUID,
        claim_count: int,
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
                        f"成功生成并保存 {claim_count} 条 Claim。"
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
        Analyst 失败时将任务标记为 FAILED。
        """
        try:
            task = self._task_service.get_task(task_id)

            if task is not None and task.status == TaskStatus.ANALYZING:
                self._task_service.transition_task_status(
                    task_id=task_id,
                    payload=TaskStatusUpdate(
                        status=TaskStatus.FAILED,
                        error_message=error_message,
                    ),
                )
        except Exception:
            pass
