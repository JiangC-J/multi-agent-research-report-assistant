from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.agent_run import AgentRunModel
from app.schemas.agent_run import (
    AgentName,
    AgentRunResponse,
    AgentRunStatus,
)


class SQLiteAgentRunRepository:
    """
    使用 SQLite 保存 Agent 执行记录。
    """

    def save(self, agent_run: AgentRunResponse) -> AgentRunResponse:
        """
        保存执行记录。

        如果记录不存在则创建；如果已存在则更新。
        """
        with SessionLocal() as session:
            database_run = session.get(
                AgentRunModel,
                str(agent_run.run_id),
            )

            if database_run is None:
                database_run = AgentRunModel(
                    run_id=str(agent_run.run_id),
                    task_id=str(agent_run.task_id),
                    agent_name=agent_run.agent_name.value,
                    status=agent_run.status.value,
                    input_summary=agent_run.input_summary,
                    output_summary=agent_run.output_summary,
                    started_at=agent_run.started_at,
                    completed_at=agent_run.completed_at,
                    duration_ms=agent_run.duration_ms,
                    input_tokens=agent_run.input_tokens,
                    output_tokens=agent_run.output_tokens,
                    estimated_cost_usd=agent_run.estimated_cost_usd,
                    error_message=agent_run.error_message,
                )
                session.add(database_run)
            else:
                database_run.status = agent_run.status.value
                database_run.output_summary = agent_run.output_summary
                database_run.completed_at = agent_run.completed_at
                database_run.duration_ms = agent_run.duration_ms
                database_run.input_tokens = agent_run.input_tokens
                database_run.output_tokens = agent_run.output_tokens
                database_run.estimated_cost_usd = agent_run.estimated_cost_usd
                database_run.error_message = agent_run.error_message

            session.commit()

        return agent_run

    def get_by_id(self, run_id: UUID) -> AgentRunResponse | None:
        """
        根据运行 ID 查询执行记录。
        """
        with SessionLocal() as session:
            database_run = session.get(
                AgentRunModel,
                str(run_id),
            )

            if database_run is None:
                return None

            return self._to_schema(database_run)

    def list_by_task_id(self, task_id: UUID) -> list[AgentRunResponse]:
        """
        查询一个研究任务的所有执行记录。

        按开始时间升序排列，便于还原执行轨迹。
        """
        with SessionLocal() as session:
            statement = (
                select(AgentRunModel)
                .where(AgentRunModel.task_id == str(task_id))
                .order_by(AgentRunModel.started_at.asc())
            )
            database_runs = session.scalars(statement).all()

            return [
                self._to_schema(database_run)
                for database_run in database_runs
            ]

    @staticmethod
    def _to_schema(database_run: AgentRunModel) -> AgentRunResponse:
        """
        将数据库模型转换为 API Schema。
        """
        return AgentRunResponse(
            run_id=UUID(database_run.run_id),
            task_id=UUID(database_run.task_id),
            agent_name=AgentName(database_run.agent_name),
            status=AgentRunStatus(database_run.status),
            input_summary=database_run.input_summary,
            output_summary=database_run.output_summary,
            started_at=database_run.started_at,
            completed_at=database_run.completed_at,
            duration_ms=database_run.duration_ms,
            input_tokens=database_run.input_tokens,
            output_tokens=database_run.output_tokens,
            estimated_cost_usd=database_run.estimated_cost_usd,
            error_message=database_run.error_message,
        )