from typing import Literal, TypedDict


class ResearchGraphState(TypedDict, total=False):
    """
    企业研究报告工作流的共享状态。

    SQLite 保存长期业务数据；
    ResearchGraphState 保存本次工作流运行期间的上下文。
    """

    # 研究任务 ID，是图与数据库之间的关联键。
    task_id: str

    # 用户输入的原始研究主题。
    task_query: str

    # Planner 生成的子任务 ID 列表。
    subtask_ids: list[str]

    # 当前即将执行的子任务下标，从 0 开始。
    current_subtask_index: int

    # 当前已经完成的子任务 ID。
    completed_subtask_ids: list[str]

    # LangGraph 当前运行阶段。
    workflow_status: Literal[
        "created",
        "planning",
        "researching",
        "analyzing",
        "reviewing",
        "awaiting_revision",
        "writing",
        "completed",
        "failed",
    ]

    # 各节点产生的简短执行记录。
    execution_log: list[str]

    # Reviewer 汇总后的任务级决策。
    review_outcome: str | None

    # Reviewer 提出的补充研究或修改要求。
    required_actions: list[str]

    # 最终生成的报告 ID。
    report_id: str | None

    # 工作流异常信息。
    error_message: str | None