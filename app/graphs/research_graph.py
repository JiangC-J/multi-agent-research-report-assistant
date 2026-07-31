from typing import Literal
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.graphs.state import ResearchGraphState
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.schemas.review_decision import TaskReviewOutcome
from app.services.analyst_execution_service import (
    AnalystExecutionService,
)
from app.services.planner_execution_service import (
    PlannerExecutionService,
)
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)
from app.services.researcher_execution_service import (
    ResearcherExecutionService,
)
from app.services.review_aggregation_service import (
    ReviewAggregationService,
)
from app.services.reviewer_execution_service import (
    ReviewerExecutionService,
)
from app.services.writer_execution_service import (
    WriterExecutionService,
)


class ResearchWorkflow:
    """
    企业多 Agent 研究报告工作流。

    这个类只负责流程编排。
    每个节点的具体业务仍由已有 ExecutionService 完成。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        planner_execution_service: PlannerExecutionService,
        researcher_execution_service: ResearcherExecutionService,
        analyst_execution_service: AnalystExecutionService,
        reviewer_execution_service: ReviewerExecutionService,
        review_aggregation_service: ReviewAggregationService,
        writer_execution_service: WriterExecutionService,
    ) -> None:
        self._task_service = task_service
        self._planner_execution_service = planner_execution_service
        self._researcher_execution_service = researcher_execution_service
        self._analyst_execution_service = analyst_execution_service
        self._reviewer_execution_service = reviewer_execution_service
        self._review_aggregation_service = review_aggregation_service
        self._writer_execution_service = writer_execution_service

    def build(self):
        """
        创建并编译 LangGraph 工作流。
        """
        builder = StateGraph(ResearchGraphState)

        # 注册节点。
        builder.add_node("initialize", self._initialize_node)
        builder.add_node("planner", self._planner_node)
        builder.add_node("researcher", self._researcher_node)
        builder.add_node("analyst", self._analyst_node)
        builder.add_node("reviewer", self._reviewer_node)
        builder.add_node(
            "review_decision",
            self._review_decision_node,
        )
        builder.add_node("writer", self._writer_node)

        # 定义主流程的固定顺序。
        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "planner")
        builder.add_edge("planner", "researcher")

        # Researcher 完成一个子任务后：
        # 可能继续执行下一个子任务，也可能进入 Analyst。
        builder.add_conditional_edges(
            "researcher",
            self._route_after_researcher,
            {
                "continue_research": "researcher",
                "start_analysis": "analyst",
            },
        )

        builder.add_edge("analyst", "reviewer")
        builder.add_edge("reviewer", "review_decision")

        # 审核汇总后：
        # 通过则写报告；
        # 返工或失败则结束当前这一轮图执行。
        builder.add_conditional_edges(
            "review_decision",
            self._route_after_review,
            {
                "write_report": "writer",
                "stop_current_run": END,
            },
        )

        builder.add_edge("writer", END)

        # LangGraph 必须 compile 后才能执行。
        return builder.compile()

    def _initialize_node(
        self,
        state: ResearchGraphState,
    ) -> dict:
        """
        初始化节点。

        验证任务存在，并把数据库任务状态从 PENDING 推进到 PLANNING。
        """
        task_id = UUID(state["task_id"])
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status not in {
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
        }:
            raise ValueError(
                "自动研究工作流只能从 PENDING 或 QUEUED 状态启动，"
                f"当前任务状态为 {task.status.value}。"
            )

        self._task_service.transition_task_status(
            task_id=task_id,
            payload=TaskStatusUpdate(
                status=TaskStatus.PLANNING,
            ),
        )

        return {
            "task_query": task.research_topic,
            "subtask_ids": [],
            "current_subtask_index": 0,
            "completed_subtask_ids": [],
            "workflow_status": "planning",
            "execution_log": [
                *state.get("execution_log", []),
                "工作流初始化完成，任务进入 PLANNING。",
            ],
            "review_outcome": None,
            "required_actions": [],
            "report_id": None,
            "error_message": None,
        }

    async def _planner_node(
        self,
        state: ResearchGraphState,
    ) -> dict:
        """
        Planner 节点。

        调用现有 PlannerExecutionService，
        生成计划并取得全部子任务 ID。
        """
        task_id = UUID(state["task_id"])

        plan = (
            await self._planner_execution_service.generate_and_save_plan(
                task_id=task_id,
            )
        )

        subtask_ids = [
            subtask.subtask_id
            for subtask in plan.subtasks
        ]

        if not subtask_ids:
            raise RuntimeError("Planner 没有生成任何研究子任务。")

        return {
            "subtask_ids": subtask_ids,
            "current_subtask_index": 0,
            "completed_subtask_ids": [],
            "workflow_status": "researching",
            "execution_log": [
                *state.get("execution_log", []),
                f"Planner 已生成 {len(subtask_ids)} 个研究子任务。",
            ],
        }

    async def _researcher_node(
        self,
        state: ResearchGraphState,
    ) -> dict:
        """
        Researcher 节点。

        每次只研究一个子任务。
        是否继续研究下一个子任务，由条件边决定。
        """
        task_id = UUID(state["task_id"])
        subtask_ids = state["subtask_ids"]
        current_index = state["current_subtask_index"]

        if current_index >= len(subtask_ids):
            raise IndexError("当前子任务下标超出计划范围。")

        current_subtask_id = subtask_ids[current_index]

        result = (
            await self._researcher_execution_service.research_subtask(
                task_id=task_id,
                subtask_id=current_subtask_id,
            )
        )

        completed_subtask_ids = [
            *state.get("completed_subtask_ids", []),
            current_subtask_id,
        ]

        return {
            "current_subtask_index": current_index + 1,
            "completed_subtask_ids": completed_subtask_ids,
            "workflow_status": "researching",
            "execution_log": [
                *state.get("execution_log", []),
                (
                    f"Researcher 已完成子任务 "
                    f"{current_subtask_id}，保存 "
                    f"{len(result.saved_evidences)} 条新证据。"
                ),
            ],
        }

    def _route_after_researcher(
        self,
        state: ResearchGraphState,
    ) -> Literal[
        "continue_research",
        "start_analysis",
    ]:
        """
        Researcher 后的条件路由。

        还有未处理子任务时，回到 Researcher；
        全部完成后，进入 Analyst。
        """
        current_index = state["current_subtask_index"]
        subtask_count = len(state["subtask_ids"])

        if current_index < subtask_count:
            return "continue_research"

        return "start_analysis"

    async def _analyst_node(
        self,
        state: ResearchGraphState,
    ) -> dict:
        """
        Analyst 节点。

        所有子任务研究完成后，先推动数据库状态进入 ANALYZING，
        再调用 AnalystExecutionService 生成 Claim。
        """
        task_id = UUID(state["task_id"])

        self._task_service.transition_task_status(
            task_id=task_id,
            payload=TaskStatusUpdate(
                status=TaskStatus.ANALYZING,
            ),
        )

        result = (
            await self._analyst_execution_service.analyze_task(
                task_id=task_id,
            )
        )

        return {
            "workflow_status": "reviewing",
            "execution_log": [
                *state.get("execution_log", []),
                (
                    f"Analyst 已完成分析，生成 "
                    f"{len(result.saved_claims)} 条 Claim。"
                ),
            ],
        }

    async def _reviewer_node(
        self,
        state: ResearchGraphState,
    ) -> dict:
        """
        Reviewer 节点。

        对所有待审核 Claim 逐条进行证据一致性审核。
        """
        task_id = UUID(state["task_id"])

        result = (
            await self._reviewer_execution_service.review_task(
                task_id=task_id,
            )
        )

        return {
    "workflow_status": "reviewing",
    "execution_log": [
        *state.get("execution_log", []),
        (
            f"Reviewer 已完成审核，共处理 "
            f"{len(result.reviews)} 条 Claim。"
        ),
    ],
}

    def _review_decision_node(
        self,
        state: ResearchGraphState,
    ) -> dict:
        """
        任务级审核决策节点。

        它不调用大模型，而是根据 Claim 审核状态执行确定性规则。
        """
        task_id = UUID(state["task_id"])

        decision = (
            self._review_aggregation_service.decide_next_step(
                task_id=task_id,
            )
        )

        if (
            decision.outcome
            == TaskReviewOutcome.PROCEED_TO_WRITING
        ):
            workflow_status = "writing"
        elif (
            decision.outcome
            == TaskReviewOutcome.RETURN_TO_RESEARCH
        ):
            workflow_status = "awaiting_revision"
        else:
            workflow_status = "failed"

        return {
            "workflow_status": workflow_status,
            "review_outcome": decision.outcome.value,
            "required_actions": decision.required_actions,
            "execution_log": [
                *state.get("execution_log", []),
                f"审核汇总决策：{decision.outcome.value}。",
            ],
        }

    def _route_after_review(
        self,
        state: ResearchGraphState,
    ) -> Literal[
        "write_report",
        "stop_current_run",
    ]:
        """
        根据审核结果决定是否进入 Writer。
        """
        if (
            state.get("review_outcome")
            == TaskReviewOutcome.PROCEED_TO_WRITING.value
        ):
            return "write_report"

        return "stop_current_run"

    async def _writer_node(
        self,
        state: ResearchGraphState,
    ) -> dict:
        """
        Writer 节点。

        只使用审核通过的 Claim 和关联 Evidence 生成最终报告。
        """
        task_id = UUID(state["task_id"])

        report = (
            await self._writer_execution_service.write_report(
                task_id=task_id,
            )
        )

        return {
            "workflow_status": "completed",
            "report_id": str(report.report_id),
            "execution_log": [
                *state.get("execution_log", []),
                f"Writer 已生成最终报告：{report.report_title}。",
            ],
        }