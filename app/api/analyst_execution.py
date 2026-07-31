from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.agents.analyst_agent import AnalystAgent
from app.clients.llm import create_chat_model
from app.repositories.sqlite_agent_run_repository import (
    SQLiteAgentRunRepository,
)
from app.repositories.sqlite_claim_repository import SQLiteClaimRepository
from app.repositories.sqlite_evidence_repository import (
    SQLiteEvidenceRepository,
)
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.analyst import AnalystExecutionResponse
from app.services.agent_run_service import AgentRunService
from app.services.analyst_execution_service import (
    AnalystExecutionError,
    AnalystExecutionService,
    AnalystTaskStatusMismatchError,
)
from app.services.claim_service import ClaimService
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/analyze",
    tags=["analyst"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

evidence_repository = SQLiteEvidenceRepository()

claim_repository = SQLiteClaimRepository()
claim_service = ClaimService(
    task_service=task_service,
    evidence_repository=evidence_repository,
    claim_repository=claim_repository,
)

agent_run_repository = SQLiteAgentRunRepository()
agent_run_service = AgentRunService(
    task_repository=task_repository,
    agent_run_repository=agent_run_repository,
)

analyst_agent = AnalystAgent(
    llm=create_chat_model(),
)

analyst_execution_service = AnalystExecutionService(
    task_service=task_service,
    evidence_repository=evidence_repository,
    claim_service=claim_service,
    agent_run_service=agent_run_service,
    analyst_agent=analyst_agent,
)


@router.post(
    "",
    response_model=AnalystExecutionResponse,
    summary="调用 Analyst 自动生成结论",
)
async def analyze_task(
    task_id: UUID,
) -> AnalystExecutionResponse:
    """
    基于已保存 Evidence 自动生成 Claim。

    成功后任务会从 ANALYZING 自动进入 REVIEWING。
    """
    try:
        return await analyst_execution_service.analyze_task(
            task_id=task_id,
        )
    except TaskNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except AnalystTaskStatusMismatchError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except AnalystExecutionError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error