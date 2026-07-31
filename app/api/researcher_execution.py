from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.agents.evidence_extraction_agent import (
    EvidenceExtractionAgent,
)
from app.agents.query_rewrite_agent import QueryRewriteAgent
from app.clients.llm import create_chat_model
from app.clients.tavily_search import (
    TavilyConfigurationError,
    TavilySearchClient,
)
from app.repositories.sqlite_agent_run_repository import (
    SQLiteAgentRunRepository,
)
from app.repositories.sqlite_evidence_repository import (
    SQLiteEvidenceRepository,
)
from app.repositories.sqlite_research_plan_repository import (
    SQLiteResearchPlanRepository,
)
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.schemas.researcher import ResearcherExecutionResponse
from app.services.agent_run_service import AgentRunService
from app.services.evidence_service import EvidenceService
from app.services.multi_query_retriever import MultiQueryRetriever
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)
from app.services.researcher_execution_service import (
    ResearcherExecutionError,
    ResearcherExecutionService,
    ResearcherSubTaskNotFoundError,
    ResearcherTaskStatusMismatchError,
)


router = APIRouter(
    prefix="/research-tasks/{task_id}/subtasks/{subtask_id}/research",
    tags=["researcher"],
)

task_repository = SQLiteTaskRepository()
task_service = ResearchTaskService(repository=task_repository)

plan_repository = SQLiteResearchPlanRepository()

agent_run_repository = SQLiteAgentRunRepository()
agent_run_service = AgentRunService(
    task_repository=task_repository,
    agent_run_repository=agent_run_repository,
)

evidence_repository = SQLiteEvidenceRepository()
evidence_service = EvidenceService(
    task_service=task_service,
    plan_repository=plan_repository,
    evidence_repository=evidence_repository,
)

llm = create_chat_model()

query_rewrite_agent = QueryRewriteAgent(llm=llm)
evidence_extraction_agent = EvidenceExtractionAgent(llm=llm)


@router.post(
    "",
    response_model=ResearcherExecutionResponse,
    summary="执行完整 Researcher 流程",
)
async def research_subtask(
    task_id: UUID,
    subtask_id: str,
) -> ResearcherExecutionResponse:
    """
    自动执行查询改写、网页检索、RRF 融合、证据提取和保存。
    """
    try:
        tavily_search_client = TavilySearchClient()

        researcher_service = ResearcherExecutionService(
            task_service=task_service,
            plan_repository=plan_repository,
            agent_run_service=agent_run_service,
            query_rewrite_agent=query_rewrite_agent,
            multi_query_retriever=MultiQueryRetriever(
                search_client=tavily_search_client,
            ),
            evidence_extraction_agent=evidence_extraction_agent,
            evidence_service=evidence_service,
        )

        return await researcher_service.research_subtask(
            task_id=task_id,
            subtask_id=subtask_id,
        )
    except (
        TaskNotFoundError,
        ResearcherSubTaskNotFoundError,
    ) as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ResearcherTaskStatusMismatchError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except TavilyConfigurationError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
    except ResearcherExecutionError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error