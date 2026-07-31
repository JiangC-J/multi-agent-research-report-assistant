import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.graphs.research_graph import ResearchWorkflow
from app.schemas.research_task import TaskStatus
from app.schemas.review_decision import TaskReviewOutcome


class FakeTaskService:
    """
    模拟任务服务。

    它不操作真实数据库，只记录状态流转，
    让我们验证工作流是否在正确阶段更新了任务状态。
    """

    def __init__(self) -> None:
        self.task = SimpleNamespace(
            research_topic="测试企业部署 AI Agent 的价值与风险",
            status=TaskStatus.PENDING,
        )
        self.transitions: list[TaskStatus] = []

    def get_task(self, task_id):
        return self.task

    def transition_task_status(self, task_id, payload):
        self.transitions.append(payload.status)
        self.task.status = payload.status


class FakePlannerExecutionService:
    """
    模拟 Planner。

    固定返回两个子任务，用来验证 Researcher 是否会循环执行两次。
    """

    def __init__(self) -> None:
        self.called = 0

    async def generate_and_save_plan(self, task_id):
        self.called += 1

        return SimpleNamespace(
            subtasks=[
                SimpleNamespace(subtask_id="subtask_1"),
                SimpleNamespace(subtask_id="subtask_2"),
            ]
        )


class FakeResearcherExecutionService:
    """
    模拟 Researcher。

    每次收到一个子任务，就记录一次调用，
    并模拟保存了两条证据。
    """

    def __init__(self) -> None:
        self.researched_subtask_ids: list[str] = []

    async def research_subtask(self, task_id, subtask_id):
        self.researched_subtask_ids.append(subtask_id)

        return SimpleNamespace(
            saved_evidences=[
                SimpleNamespace(),
                SimpleNamespace(),
            ]
        )


class FakeAnalystExecutionService:
    """模拟 Analyst，固定生成两条 Claim。"""

    def __init__(self) -> None:
        self.called = 0

    async def analyze_task(self, task_id):
        self.called += 1

        return SimpleNamespace(
            saved_claims=[
                SimpleNamespace(),
                SimpleNamespace(),
            ]
        )


class FakeReviewerExecutionService:
    """模拟 Reviewer，固定完成两条 Claim 的审核。"""

    def __init__(self) -> None:
        self.called = 0

    async def review_task(self, task_id):
        self.called += 1

        return SimpleNamespace(
            reviews=[
                SimpleNamespace(),
                SimpleNamespace(),
            ]
        )


class FakeReviewAggregationService:
    """
    模拟任务级审核决策。

    outcome 由构造函数传入，
    因此同一套工作流可以测试“生成报告”和“停止等待返工”两条分支。
    """

    def __init__(self, outcome: TaskReviewOutcome) -> None:
        self.outcome = outcome
        self.called = 0

    def decide_next_step(self, task_id):
        self.called += 1

        return SimpleNamespace(
            outcome=self.outcome,
            required_actions=["补充来源可靠性说明"],
        )


class FakeWriterExecutionService:
    """模拟 Writer，固定返回一个报告 ID。"""

    def __init__(self) -> None:
        self.called = 0

    async def write_report(self, task_id):
        self.called += 1

        return SimpleNamespace(
            report_id=uuid4(),
            report_title="测试研究报告",
        )


def build_workflow(
    review_outcome: TaskReviewOutcome,
):
    """
    组装一条完全不依赖真实外部服务的工作流。

    返回 workflow 和各替身对象，
    让测试既能断言最终结果，也能断言每个 Agent 实际被调用了几次。
    """
    task_service = FakeTaskService()
    planner_service = FakePlannerExecutionService()
    researcher_service = FakeResearcherExecutionService()
    analyst_service = FakeAnalystExecutionService()
    reviewer_service = FakeReviewerExecutionService()
    aggregation_service = FakeReviewAggregationService(
        outcome=review_outcome,
    )
    writer_service = FakeWriterExecutionService()

    workflow = ResearchWorkflow(
        task_service=task_service,
        planner_execution_service=planner_service,
        researcher_execution_service=researcher_service,
        analyst_execution_service=analyst_service,
        reviewer_execution_service=reviewer_service,
        review_aggregation_service=aggregation_service,
        writer_execution_service=writer_service,
    ).build()

    return (
        workflow,
        task_service,
        planner_service,
        researcher_service,
        analyst_service,
        reviewer_service,
        aggregation_service,
        writer_service,
    )


def create_initial_state(task_id: str) -> dict:
    """构造与 API 层一致的工作流初始状态。"""
    return {
        "task_id": task_id,
        "workflow_status": "created",
        "subtask_ids": [],
        "current_subtask_index": 0,
        "completed_subtask_ids": [],
        "execution_log": [],
        "review_outcome": None,
        "required_actions": [],
        "report_id": None,
        "error_message": None,
    }


def test_workflow_writes_report_after_review_approval():
    """
    审核通过时：
    两个子任务都应被研究，随后分析、审核、写报告，
    最终工作流状态应为 completed。
    """
    (
        workflow,
        task_service,
        planner_service,
        researcher_service,
        analyst_service,
        reviewer_service,
        aggregation_service,
        writer_service,
    ) = build_workflow(
        TaskReviewOutcome.PROCEED_TO_WRITING,
    )

    result = asyncio.run(
        workflow.ainvoke(
            create_initial_state(str(uuid4())),
            config={"recursion_limit": 30},
        )
    )

    assert result["workflow_status"] == "completed"
    assert result["completed_subtask_ids"] == [
        "subtask_1",
        "subtask_2",
    ]
    assert result["report_id"] is not None

    assert planner_service.called == 1
    assert researcher_service.researched_subtask_ids == [
        "subtask_1",
        "subtask_2",
    ]
    assert analyst_service.called == 1
    assert reviewer_service.called == 1
    assert aggregation_service.called == 1
    assert writer_service.called == 1

    assert task_service.transitions == [
        TaskStatus.PLANNING,
        TaskStatus.ANALYZING,
    ]


def test_workflow_stops_when_review_requires_more_research():
    """
    审核要求返工时：
    图应停在 awaiting_revision，
    Writer 不允许被调用，避免依据未通过审核的结论生成报告。
    """
    (
        workflow,
        _task_service,
        _planner_service,
        _researcher_service,
        _analyst_service,
        _reviewer_service,
        _aggregation_service,
        writer_service,
    ) = build_workflow(
        TaskReviewOutcome.RETURN_TO_RESEARCH,
    )

    result = asyncio.run(
        workflow.ainvoke(
            create_initial_state(str(uuid4())),
            config={"recursion_limit": 30},
        )
    )

    assert result["workflow_status"] == "awaiting_revision"
    assert result["review_outcome"] == (
        TaskReviewOutcome.RETURN_TO_RESEARCH.value
    )
    assert result["report_id"] is None
    assert writer_service.called == 0