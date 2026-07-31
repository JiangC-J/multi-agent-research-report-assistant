from typing import Protocol
from uuid import UUID

from app.schemas.agent_run import AgentRunResponse


class AgentRunRepository(Protocol):
    """
    Agent 执行记录的数据访问约定。
    """

    def save(self, agent_run: AgentRunResponse) -> AgentRunResponse:
        """
        保存一条 Agent 执行记录。
        """

    def get_by_id(self, run_id: UUID) -> AgentRunResponse | None:
        """
        根据运行 ID 查询一条执行记录。
        """

    def list_by_task_id(self, task_id: UUID) -> list[AgentRunResponse]:
        """
        查询某个研究任务的全部执行记录。
        """