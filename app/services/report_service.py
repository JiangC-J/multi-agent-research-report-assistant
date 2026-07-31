from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.repositories.claim_repository import ClaimRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.report_repository import ReportRepository
from app.schemas.claim import ClaimReviewStatus
from app.schemas.report import (
    ReportDraft,
    ReportResponse,
    ReportStatus,
)
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.services.report_renderer import render_markdown_report
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class ReportTaskStatusMismatchError(Exception):
    """
    任务不处于 WRITING 状态时抛出。
    """


class ReportAlreadyExistsError(Exception):
    """
    一个任务重复生成报告时抛出。
    """


class InvalidReportClaimError(Exception):
    """
    报告引用的 Claim 不存在、不属于当前任务或未通过审核时抛出。
    """


class InvalidReportCitationError(Exception):
    """
    Citation 与 Claim、Evidence 的绑定不正确时抛出。
    """


class ReportService:
    """
    报告生成和保存的业务服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        claim_repository: ClaimRepository,
        evidence_repository: EvidenceRepository,
        report_repository: ReportRepository,
    ) -> None:
        self._task_service = task_service
        self._claim_repository = claim_repository
        self._evidence_repository = evidence_repository
        self._report_repository = report_repository

    def create_report(
        self,
        task_id: UUID,
        payload: ReportDraft,
    ) -> ReportResponse:
        """
        校验并保存一份最终 Markdown 报告。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.WRITING:
            raise ReportTaskStatusMismatchError(
                "只有 WRITING 状态的任务可以生成报告；"
                f"当前状态为 {task.status.value}。"
            )

        existing_report = self._report_repository.get_by_task_id(task_id)

        if existing_report is not None:
            raise ReportAlreadyExistsError(
                "当前研究任务已经存在最终报告。"
            )

        task_claims = self._claim_repository.list_by_task_id(task_id)

        claims_by_id = {
            claim.claim_id: claim
            for claim in task_claims
        }

        section_claim_ids = {
            claim_id
            for section in payload.sections
            for claim_id in section.claim_ids
        }

        invalid_claim_ids = [
            claim_id
            for claim_id in section_claim_ids
            if claim_id not in claims_by_id
            or claims_by_id[claim_id].review_status
            != ClaimReviewStatus.APPROVED
        ]

        if invalid_claim_ids:
            raise InvalidReportClaimError(
                "报告只能使用属于当前任务且已审核通过的 Claim。"
            )

        task_evidences = self._evidence_repository.list_by_task_id(task_id)

        evidences_by_id = {
            evidence.evidence_id: evidence
            for evidence in task_evidences
        }

        cited_claim_ids: set[UUID] = set()

        for citation in payload.citations:
            evidence = evidences_by_id.get(citation.evidence_id)

            if evidence is None:
                raise InvalidReportCitationError(
                    "Citation 引用了不存在或不属于当前任务的 Evidence。"
                )

            for claim_id in citation.claim_ids:
                claim = claims_by_id.get(claim_id)

                if (
                    claim is None
                    or claim.review_status
                    != ClaimReviewStatus.APPROVED
                    or citation.evidence_id not in claim.evidence_ids
                ):
                    raise InvalidReportCitationError(
                        "Citation 必须使用已审核通过 Claim "
                        "已绑定的 Evidence。"
                    )

                cited_claim_ids.add(claim_id)

        uncited_claim_ids = section_claim_ids - cited_claim_ids

        if uncited_claim_ids:
            raise InvalidReportCitationError(
                "每条出现在报告章节中的 Claim "
                "至少需要一条 Citation。"
            )

        markdown_content = render_markdown_report(
            report=payload,
            evidences_by_id=evidences_by_id,
        )

        report = ReportResponse(
            report_id=uuid4(),
            task_id=task_id,
            status=ReportStatus.COMPLETED,
            report_title=payload.report_title,
            sections=payload.sections,
            citations=payload.citations,
            markdown_content=markdown_content,
            created_at=datetime.now(timezone.utc),
        )

        saved_report = self._report_repository.create(report)

        self._task_service.transition_task_status(
            task_id=task_id,
            payload=TaskStatusUpdate(
                status=TaskStatus.COMPLETED,
            ),
        )

        return saved_report

    def get_report_by_task_id(
        self,
        task_id: UUID,
    ) -> ReportResponse:
        """
        查询指定任务的最终报告。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        report = self._report_repository.get_by_task_id(task_id)

        if report is None:
            raise ReportNotFoundError("最终报告不存在。")

        return report


class ReportNotFoundError(Exception):
    """
    查询不到最终报告时抛出。
    """