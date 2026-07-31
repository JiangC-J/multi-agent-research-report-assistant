from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.agents.writer_agent import WriterAgent
from app.clients.llm import create_chat_model
from app.repositories.sqlite_agent_run_repository import (
    SQLiteAgentRunRepository,
)
from app.repositories.sqlite_claim_repository import SQLiteClaimRepository
from app.repositories.sqlite_evidence_repository import (
    SQLiteEvidenceRepository,
)
from app.repositories.sqlite_report_repository import SQLiteReportRepository
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.report import ReportResponse
from app.services.agent_run_service import AgentRunService
from app.services.report_service import ReportService
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)
from app.services.writer_execution_service import (
    WriterExecutionError,
    WriterExecutionService,
    WriterTaskStatusMismatchError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/write",
    tags=["writer"],
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

agent_run_repository = SQLiteAgentRunRepository()
agent_run_service = AgentRunService(
    task_repository=task_repository,
    agent_run_repository=agent_run_repository,
)

writer_agent = WriterAgent(
    llm=create_chat_model(),
)

writer_execution_service = WriterExecutionService(
    task_service=task_service,
    claim_repository=claim_repository,
    evidence_repository=evidence_repository,
    report_service=report_service,
    agent_run_service=agent_run_service,
    writer_agent=writer_agent,
)


@router.post(
    "",
    response_model=ReportResponse,
    summary="调用 Writer 自动生成最终报告",
)
async def write_report(
    task_id: UUID,
) -> ReportResponse:
    """
    基于 APPROVED Claim 自动生成最终 Markdown 报告。

    成功后任务会从 WRITING 自动进入 COMPLETED。
    """
    try:
        return await writer_execution_service.write_report(
            task_id=task_id,
        )
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except WriterTaskStatusMismatchError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except WriterExecutionError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error