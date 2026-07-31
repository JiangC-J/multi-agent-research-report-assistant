from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.repositories.sqlite_claim_repository import SQLiteClaimRepository
from app.repositories.sqlite_evidence_repository import (
    SQLiteEvidenceRepository,
)
from app.repositories.sqlite_report_repository import SQLiteReportRepository
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.report import ReportDraft, ReportResponse
from app.services.report_service import (
    InvalidReportCitationError,
    InvalidReportClaimError,
    ReportAlreadyExistsError,
    ReportNotFoundError,
    ReportService,
    ReportTaskStatusMismatchError,
)
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/report",
    tags=["reports"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

claim_repository = SQLiteClaimRepository()
evidence_repository = SQLiteEvidenceRepository()
report_repository = SQLiteReportRepository()

report_service = ReportService(
    task_service=task_service,
    claim_repository=claim_repository,
    evidence_repository=evidence_repository,
    report_repository=report_repository,
)


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="生成最终报告（开发调试）",
)
async def create_report(
    task_id: UUID,
    payload: ReportDraft,
) -> ReportResponse:
    """
    当前用于模拟 Writer 生成最终报告。

    后续由 Writer Agent 自动调用。
    """
    try:
        return report_service.create_report(
            task_id=task_id,
            payload=payload,
        )
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (
        ReportTaskStatusMismatchError,
        ReportAlreadyExistsError,
        InvalidReportClaimError,
        InvalidReportCitationError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=ReportResponse,
    summary="查询最终报告",
)
async def get_report(task_id: UUID) -> ReportResponse:
    """
    查询指定任务的最终 Markdown 报告。
    """
    try:
        return report_service.get_report_by_task_id(task_id)
    except (TaskNotFoundError, ReportNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error