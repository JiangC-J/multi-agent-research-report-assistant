from functools import lru_cache
from app.clients.redis_client import get_redis_client
from app.core.config import get_settings
from app.services.search_cache_service import SearchCacheService

from app.agents.analyst_agent import AnalystAgent
from app.agents.evidence_extraction_agent import (
    EvidenceExtractionAgent,
)
from app.agents.planner_agent import PlannerAgent
from app.agents.query_rewrite_agent import QueryRewriteAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.writer_agent import WriterAgent
from app.clients.llm import create_chat_model
from app.clients.tavily_search import TavilySearchClient
from app.graphs.research_graph import ResearchWorkflow
from app.repositories.sqlite_agent_run_repository import (
    SQLiteAgentRunRepository,
)
from app.repositories.sqlite_claim_repository import (
    SQLiteClaimRepository,
)
from app.repositories.sqlite_evidence_repository import (
    SQLiteEvidenceRepository,
)
from app.repositories.sqlite_report_repository import (
    SQLiteReportRepository,
)
from app.repositories.sqlite_research_plan_repository import (
    SQLiteResearchPlanRepository,
)
from app.repositories.sqlite_review_repository import (
    SQLiteReviewRepository,
)
from app.repositories.sqlite_task_repository import (
    SQLiteTaskRepository,
)
from app.services.agent_run_service import AgentRunService
from app.services.analyst_execution_service import (
    AnalystExecutionService,
)
from app.services.claim_service import ClaimService
from app.services.evidence_service import EvidenceService
from app.services.multi_query_retriever import MultiQueryRetriever
from app.services.planner_execution_service import (
    PlannerExecutionService,
)
from app.services.report_service import ReportService
from app.services.research_plan_service import ResearchPlanService
from app.services.research_task_service import ResearchTaskService
from app.services.researcher_execution_service import (
    ResearcherExecutionService,
)
from app.services.review_aggregation_service import (
    ReviewAggregationService,
)
from app.services.reviewer_execution_service import (
    ReviewerExecutionService,
)
from app.services.review_service import ReviewService
from app.services.writer_execution_service import (
    WriterExecutionService,
)


@lru_cache(maxsize=1)
def create_research_workflow():
    """
    创建并缓存完整的企业研究工作流。

    这个函数是工作流层的依赖装配入口：
    Repository -> Service -> Agent -> ExecutionService -> LangGraph。
    """

    # ---------------------------------------------------------
    # 第一层：Repository
    # ---------------------------------------------------------
    # Repository 负责持久化，不包含大模型逻辑和流程逻辑。

    task_repository = SQLiteTaskRepository()
    agent_run_repository = SQLiteAgentRunRepository()
    plan_repository = SQLiteResearchPlanRepository()
    evidence_repository = SQLiteEvidenceRepository()
    claim_repository = SQLiteClaimRepository()
    review_repository = SQLiteReviewRepository()
    report_repository = SQLiteReportRepository()

    # ---------------------------------------------------------
    # 第二层：基础业务 Service
    # ---------------------------------------------------------
    # 这些 Service 负责状态校验、引用校验和数据保存。

    task_service = ResearchTaskService(
        repository=task_repository,
    )

    agent_run_service = AgentRunService(
        task_repository=task_repository,
        agent_run_repository=agent_run_repository,
    )

    research_plan_service = ResearchPlanService(
        task_service=task_service,
        plan_repository=plan_repository,
    )

    evidence_service = EvidenceService(
        task_service=task_service,
        plan_repository=plan_repository,
        evidence_repository=evidence_repository,
    )

    claim_service = ClaimService(
        task_service=task_service,
        evidence_repository=evidence_repository,
        claim_repository=claim_repository,
    )

    review_service = ReviewService(
        task_service=task_service,
        claim_repository=claim_repository,
        review_repository=review_repository,
    )

    report_service = ReportService(
        task_service=task_service,
        claim_repository=claim_repository,
        evidence_repository=evidence_repository,
        report_repository=report_repository,
    )

    # ---------------------------------------------------------
    # 第三层：外部客户端
    # ---------------------------------------------------------
    # 一个 LLM 客户端可以被多个 Agent 复用。
    # 每个 Agent 仍有独立的 Prompt、Schema 和职责。

    llm = create_chat_model()

    settings = get_settings()

    search_cache_service = SearchCacheService(
        redis_client=get_redis_client(),
        ttl_seconds=settings.search_cache_ttl_seconds,
    )

    tavily_search_client = TavilySearchClient(
        search_cache_service=search_cache_service,
    )

    multi_query_retriever = MultiQueryRetriever(
        search_client=tavily_search_client,
    )

    # ---------------------------------------------------------
    # 第四层：Agent
    # ---------------------------------------------------------
    # Agent 负责模型推理，不直接决定整个任务的流程。

    planner_agent = PlannerAgent(
        llm=llm,
    )

    query_rewrite_agent = QueryRewriteAgent(
        llm=llm,
    )

    evidence_extraction_agent = EvidenceExtractionAgent(
        llm=llm,
    )

    analyst_agent = AnalystAgent(
        llm=llm,
    )

    reviewer_agent = ReviewerAgent(
        llm=llm,
    )

    writer_agent = WriterAgent(
        llm=llm,
    )

    # ---------------------------------------------------------
    # 第五层：Agent ExecutionService
    # ---------------------------------------------------------
    # ExecutionService 把一次 Agent 调用包装为完整业务操作：
    # 状态检查、AgentRun 审计、模型调用、结果保存、异常处理。

    planner_execution_service = PlannerExecutionService(
        task_service=task_service,
        agent_run_service=agent_run_service,
        research_plan_service=research_plan_service,
        planner_agent=planner_agent,
    )

    researcher_execution_service = ResearcherExecutionService(
        task_service=task_service,
        plan_repository=plan_repository,
        agent_run_service=agent_run_service,
        query_rewrite_agent=query_rewrite_agent,
        multi_query_retriever=multi_query_retriever,
        evidence_extraction_agent=evidence_extraction_agent,
        evidence_service=evidence_service,
    )

    analyst_execution_service = AnalystExecutionService(
        task_service=task_service,
        evidence_repository=evidence_repository,
        claim_service=claim_service,
        agent_run_service=agent_run_service,
        analyst_agent=analyst_agent,
    )

    reviewer_execution_service = ReviewerExecutionService(
        task_service=task_service,
        claim_repository=claim_repository,
        evidence_repository=evidence_repository,
        review_service=review_service,
        agent_run_service=agent_run_service,
        reviewer_agent=reviewer_agent,
    )

    review_aggregation_service = ReviewAggregationService(
        task_service=task_service,
        claim_repository=claim_repository,
        review_repository=review_repository,
        agent_run_repository=agent_run_repository,
        max_review_iterations=2,
    )

    writer_execution_service = WriterExecutionService(
        task_service=task_service,
        claim_repository=claim_repository,
        evidence_repository=evidence_repository,
        report_service=report_service,
        agent_run_service=agent_run_service,
        writer_agent=writer_agent,
    )

    # ---------------------------------------------------------
    # 第六层：LangGraph 工作流
    # ---------------------------------------------------------
    # LangGraph 只负责节点顺序、循环和条件路由。

    workflow = ResearchWorkflow(
        task_service=task_service,
        planner_execution_service=planner_execution_service,
        researcher_execution_service=researcher_execution_service,
        analyst_execution_service=analyst_execution_service,
        reviewer_execution_service=reviewer_execution_service,
        review_aggregation_service=review_aggregation_service,
        writer_execution_service=writer_execution_service,
    )

    return workflow.build()