from typing import Any
from uuid import UUID

from fastmcp import FastMCP

from app.repositories.sqlite_agent_run_repository import SQLiteAgentRunRepository
from app.repositories.sqlite_claim_repository import SQLiteClaimRepository
from app.repositories.sqlite_evidence_repository import SQLiteEvidenceRepository
from app.repositories.sqlite_report_repository import SQLiteReportRepository
from app.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.repositories.sqlite_workflow_run_repository import (
    SQLiteWorkflowRunRepository,
)
from app.services.agent_run_service import (
    AgentRunService,
    ResearchTaskNotFoundError,
)
from app.services.report_service import (
    ReportNotFoundError,
    ReportService,
)
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)
from app.services.workflow_run_service import (
    WorkflowRunService,
    WorkflowRunTaskNotFoundError,
)


mcp = FastMCP("Enterprise Research Assistant")


def get_research_task_service() -> ResearchTaskService:
    """
    创建研究任务服务。

    MCP 层只负责协议适配；
    真正的任务查询仍交给既有 Service 和 Repository 完成。
    """
    repository = SQLiteTaskRepository()
    return ResearchTaskService(repository)


def get_report_service() -> ReportService:
    """
    创建报告服务。

    ReportService 负责保证报告、Claim 和 Evidence 的关系
    与 Web API、Celery Worker 中使用的规则保持一致。
    """
    task_service = get_research_task_service()

    return ReportService(
        task_service=task_service,
        claim_repository=SQLiteClaimRepository(),
        evidence_repository=SQLiteEvidenceRepository(),
        report_repository=SQLiteReportRepository(),
    )


def get_workflow_run_service() -> WorkflowRunService:
    """
    创建工作流执行记录服务。

    一条 WorkflowRun 对应一次 Celery 后台工作流尝试。
    """
    return WorkflowRunService(
        task_repository=SQLiteTaskRepository(),
        workflow_run_repository=SQLiteWorkflowRunRepository(),
    )


def get_agent_run_service() -> AgentRunService:
    """
    创建 Agent 执行记录服务。

    一条 AgentRun 对应某个 Agent 的一次执行记录。
    """
    return AgentRunService(
        task_repository=SQLiteTaskRepository(),
        agent_run_repository=SQLiteAgentRunRepository(),
    )


def read_research_task(task_id: str) -> dict[str, Any]:
    """
    普通业务函数：根据任务 ID 查询研究任务。

    它不依赖 MCP，因此既可被 MCP Tool、Resource 调用，
    也可被单元测试或其他 Python 代码直接调用。
    """
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        return {
            "ok": False,
            "error": "task_id 格式不正确，必须是合法的 UUID。",
        }

    task_service = get_research_task_service()
    task = task_service.get_task(task_uuid)

    if task is None:
        return {
            "ok": False,
            "error": "未找到对应的研究任务。",
            "task_id": task_id,
        }

    return {
        "ok": True,
        "task": task.model_dump(mode="json"),
    }


def read_final_report(task_id: str) -> dict[str, Any]:
    """
    普通业务函数：查询最终报告，并补充每条引用对应的真实来源。

    返回内容包括：
    1. 报告结构化章节；
    2. 可直接展示或导出的 Markdown；
    3. citation_key 与来源 URL、标题、证据摘要的映射。
    """
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        return {
            "ok": False,
            "error": "task_id 格式不正确，必须是合法的 UUID。",
        }

    report_service = get_report_service()

    try:
        report = report_service.get_report_by_task_id(task_uuid)
    except TaskNotFoundError:
        return {
            "ok": False,
            "error": "未找到对应的研究任务。",
            "task_id": task_id,
        }
    except ReportNotFoundError:
        return {
            "ok": False,
            "error": "该任务尚未生成最终报告。",
            "task_id": task_id,
        }

    evidence_repository = SQLiteEvidenceRepository()
    evidences = evidence_repository.list_by_task_id(task_uuid)
    evidences_by_id = {
        evidence.evidence_id: evidence
        for evidence in evidences
    }

    sources: list[dict[str, Any]] = []

    for citation in report.citations:
        evidence = evidences_by_id.get(citation.evidence_id)

        if evidence is None:
            continue

        sources.append(
            {
                "citation_key": citation.citation_key,
                "evidence_id": str(evidence.evidence_id),
                "claim_ids": [
                    str(claim_id)
                    for claim_id in citation.claim_ids
                ],
                "source_title": evidence.source_title,
                "source_url": str(evidence.source_url),
                "source_type": evidence.source_type.value,
                "source_quality_hint": (
                    evidence.source_quality_hint.value
                ),
                "evidence_summary": evidence.evidence_summary,
            }
        )

    return {
        "ok": True,
        "report": report.model_dump(mode="json"),
        "sources": sources,
    }


def read_execution_trace(task_id: str) -> dict[str, Any]:
    """
    普通业务函数：查询任务的完整执行审计轨迹。

    包含 Celery 工作流执行记录和各 Agent 的执行记录，
    用于排障、性能分析、成本分析与结果追溯。
    """
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        return {
            "ok": False,
            "error": "task_id 格式不正确，必须是合法的 UUID。",
        }

    workflow_run_service = get_workflow_run_service()
    agent_run_service = get_agent_run_service()

    try:
        workflow_runs = workflow_run_service.list_runs_by_task_id(
            task_uuid
        )
    except WorkflowRunTaskNotFoundError:
        return {
            "ok": False,
            "error": "未找到对应的研究任务。",
            "task_id": task_id,
        }

    try:
        agent_runs = agent_run_service.list_runs_by_task_id(task_uuid)
    except ResearchTaskNotFoundError:
        return {
            "ok": False,
            "error": "未找到对应的研究任务。",
            "task_id": task_id,
        }

    total_duration_ms = sum(
        run.duration_ms or 0
        for run in agent_runs
    )
    total_estimated_cost_usd = round(
        sum(
            run.estimated_cost_usd
            for run in agent_runs
        ),
        6,
    )

    return {
        "ok": True,
        "task_id": task_id,
        "workflow_runs": [
            run.model_dump(mode="json")
            for run in workflow_runs
        ],
        "agent_runs": [
            run.model_dump(mode="json")
            for run in agent_runs
        ],
        "metrics": {
            "agent_run_count": len(agent_runs),
            "total_agent_duration_ms": total_duration_ms,
            "total_estimated_cost_usd": total_estimated_cost_usd,
        },
    }


def build_report_review_prompt(
    task_id: str,
    audience: str = "企业管理者",
) -> str:
    """
    生成报告审阅提示词。

    保持为普通函数，便于单独测试；
    MCP Prompt 仅负责将其暴露给客户端。
    """
    return f"""
你是一名企业 AI 应用战略顾问。请面向“{audience}”审阅研究任务
“{task_id}”的最终报告。

请严格按以下步骤工作：

1. 调用 get_research_task，确认任务状态必须为 COMPLETED。
2. 调用 get_final_report，获取报告章节、Markdown 内容和 sources。
3. 调用 get_execution_trace，查看 Planner、Researcher、Analyst、
   Reviewer、Writer 的执行状态、耗时和预估成本。
4. 输出一份结构化审阅意见，必须包含：
   - 核心结论：提炼报告中最值得决策者关注的三点；
   - 主要风险：区分事实证据支持的风险与需要进一步验证的推测；
   - 落地建议：按“近期试点、治理与安全、规模化”组织建议；
   - 来源核验：引用 sources 中的 source_title 和 source_url；
   - 执行评估：说明工作流是否成功、总 Agent 耗时和预估成本；
   - 局限性：明确资料来源、时间范围和证据质量的限制。

约束：
- 不得编造 sources 中不存在的来源或数据。
- 不得把证据摘要扩写成未经验证的事实。
- 当来源质量为 LOW 或缺少充分来源时，必须明确标注不确定性。
- 使用清晰、面向业务决策的中文表达。
""".strip()


@mcp.tool
def get_research_task(task_id: str) -> dict[str, Any]:
    """
    根据任务 ID 查询企业研究任务的当前状态、主题、要求和错误信息。

    Args:
        task_id: 研究任务 UUID。
    """
    return read_research_task(task_id)


@mcp.tool
def get_final_report(task_id: str) -> dict[str, Any]:
    """
    查询已完成研究任务的最终报告、Markdown 内容及其可追溯引用来源。

    Args:
        task_id: 已生成最终报告的研究任务 UUID。
    """
    return read_final_report(task_id)


@mcp.tool
def get_execution_trace(task_id: str) -> dict[str, Any]:
    """
    查询研究任务的工作流和多 Agent 执行审计轨迹。

    返回工作流状态、各 Agent 状态、执行耗时、Token、
    预估成本及错误信息，仅用于读取和排障。

    Args:
        task_id: 研究任务 UUID。
    """
    return read_execution_trace(task_id)


@mcp.resource(
    "research://tasks/{task_id}/summary",
    name="ResearchTaskSummary",
    description="读取指定研究任务的只读摘要与当前状态。",
    mime_type="application/json",
)
def get_research_task_summary_resource(
    task_id: str,
) -> dict[str, Any]:
    """
    通过 URI 读取研究任务摘要。

    例如：
    research://tasks/2a73a041-3048-4301-9c78-73d920ed424d/summary
    """
    return read_research_task(task_id)


@mcp.prompt(
    name="review_research_report",
    description="生成面向企业管理者的研究报告审阅工作指令。",
)
def review_research_report(
    task_id: str,
    audience: str = "企业管理者",
) -> str:
    """
    引导客户端中的 LLM 调用任务、报告与审计 Tool，
    并产出一份带来源和不确定性声明的报告审阅意见。
    """
    return build_report_review_prompt(
        task_id=task_id,
        audience=audience,
    )


if __name__ == "__main__":
    mcp.run()