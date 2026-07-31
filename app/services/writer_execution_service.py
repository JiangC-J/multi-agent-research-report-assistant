from uuid import UUID

from app.agents.writer_agent import WriterAgent
from app.repositories.claim_repository import ClaimRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.agent_run import (
    AgentName,
    AgentRunFinish,
    AgentRunStart,
    AgentRunStatus,
)
from app.schemas.claim import ClaimReviewStatus
from app.schemas.report import ReportResponse
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.services.agent_run_service import AgentRunService
from app.services.report_service import ReportService
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class WriterTaskStatusMismatchError(Exception):
    """
    任务不处于 WRITING 状态时抛出。
    """


class WriterExecutionError(Exception):
    """
    Writer 执行失败时抛出。
    """


class WriterExecutionService:
    """
    Writer 的完整执行编排服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        claim_repository: ClaimRepository,
        evidence_repository: EvidenceRepository,
        report_service: ReportService,
        agent_run_service: AgentRunService,
        writer_agent: WriterAgent,
    ) -> None:
        self._task_service = task_service
        self._claim_repository = claim_repository
        self._evidence_repository = evidence_repository
        self._report_service = report_service
        self._agent_run_service = agent_run_service
        self._writer_agent = writer_agent

    async def write_report(
        self,
        task_id: UUID,
    ) -> ReportResponse:
        """
        根据 APPROVED Claim 自动生成、保存并完成最终报告。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.WRITING:
            raise WriterTaskStatusMismatchError(
                "只有 WRITING 状态的任务可以执行 Writer；"
                f"当前状态为 {task.status.value}。"
            )

        claims = self._claim_repository.list_by_task_id(task_id)

        approved_claims = [
            claim
            for claim in claims
            if claim.review_status == ClaimReviewStatus.APPROVED
        ]

        if not approved_claims:
            raise WriterExecutionError(
                "当前任务没有 APPROVED Claim，无法生成报告。"
            )

        all_evidences = self._evidence_repository.list_by_task_id(
            task_id
        )
        evidences_by_id = {
            evidence.evidence_id: evidence
            for evidence in all_evidences
        }

        required_evidence_ids = {
            evidence_id
            for claim in approved_claims
            for evidence_id in claim.evidence_ids
        }

        missing_evidence_ids = [
            evidence_id
            for evidence_id in required_evidence_ids
            if evidence_id not in evidences_by_id
        ]

        if missing_evidence_ids:
            raise WriterExecutionError(
                "部分 APPROVED Claim 绑定的 Evidence 不存在。"
            )

        agent_run = self._agent_run_service.start_run(
            task_id=task_id,
            payload=AgentRunStart(
                agent_name=AgentName.WRITER,
                input_summary=(
                    f"基于 {len(approved_claims)} 条 APPROVED Claim "
                    "生成最终 Markdown 报告。"
                ),
            ),
        )

        try:
            agent_result = await self._writer_agent.write_report(
                research_topic=task.research_topic,
                requirements=task.requirements,
                approved_claims=approved_claims,
                evidences_by_id=evidences_by_id,
            )

            saved_report = self._report_service.create_report(
                task_id=task_id,
                payload=agent_result.report_draft,
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

            raise WriterExecutionError(
                f"Writer 执行失败：{error_message}"
            ) from error

        self._safe_finish_succeeded_run(
            run_id=agent_run.run_id,
            report_title=saved_report.report_title,
            input_tokens=agent_result.input_tokens,
            output_tokens=agent_result.output_tokens,
        )

        return saved_report

    def _safe_finish_succeeded_run(
        self,
        run_id: UUID,
        report_title: str,
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
                        f"成功生成最终报告《{report_title}》。"
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
        Writer 失败时将仍处于 WRITING 的任务标记为 FAILED。
        """
        try:
            task = self._task_service.get_task(task_id)

            if task is not None and task.status == TaskStatus.WRITING:
                self._task_service.transition_task_status(
                    task_id=task_id,
                    payload=TaskStatusUpdate(
                        status=TaskStatus.FAILED,
                        error_message=error_message,
                    ),
                )
        except Exception:
            pass
