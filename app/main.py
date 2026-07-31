from contextlib import asynccontextmanager
from app.api.background_tasks import (
    router as background_tasks_router,
)
from fastapi import FastAPI
from app.api.workflow_runs import (
    router as workflow_runs_router,
)
from app.api.agent_runs import router as agent_runs_router
from app.api.analyst_execution import router as analyst_execution_router
from app.api.claims import router as claims_router
from app.api.evidences import router as evidences_router
from app.api.planner_execution import router as planner_execution_router
from app.api.query_rewrite_execution import (
    router as query_rewrite_execution_router,
)
from app.api.reports import router as reports_router
from app.api.research_plans import router as research_plans_router
from app.api.research_tasks import router as research_tasks_router
from app.api.researcher_execution import router as researcher_execution_router
from app.api.retrieval import router as retrieval_router
from app.api.review_decision import router as review_decision_router
from app.api.reviewer_execution import router as reviewer_execution_router
from app.api.reviews import router as reviews_router
from app.api.search import router as search_router
from app.api.workflows import router as workflows_router
from app.api.writer_execution import router as writer_execution_router
from app.clients.redis_client import close_redis_client
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期管理。

    启动时初始化 SQLite；
    停止时释放 Redis 连接池。
    """
    init_db()

    try:
        yield
    finally:
        await close_redis_client()


app = FastAPI(
    title="企业多 Agent 研究报告助手",
    description="一个用于生成带来源研究报告的多 Agent 系统。",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(research_tasks_router)
app.include_router(workflows_router)
app.include_router(workflow_runs_router)
app.include_router(background_tasks_router)

# 以下接口保留为调试接口。
# 它们适合单独验证某个 Agent 或某个业务环节。
app.include_router(agent_runs_router)
app.include_router(research_plans_router)
app.include_router(evidences_router)
app.include_router(claims_router)
app.include_router(reviews_router)
app.include_router(reports_router)
app.include_router(planner_execution_router)
app.include_router(query_rewrite_execution_router)
app.include_router(search_router)
app.include_router(retrieval_router)
app.include_router(researcher_execution_router)
app.include_router(analyst_execution_router)
app.include_router(reviewer_execution_router)
app.include_router(review_decision_router)
app.include_router(writer_execution_router)


@app.get(
    "/health",
    tags=["system"],
    summary="健康检查",
)
async def health_check() -> dict[str, str]:
    """
    用于确认 API 服务是否正常运行。
    """
    return {
        "status": "ok",
        "service": "multi-agent-research-assistant",
        "version": "0.1.0",
    }