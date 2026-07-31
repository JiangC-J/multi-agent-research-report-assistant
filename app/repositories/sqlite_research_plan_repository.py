from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.research_plan import (
    ResearchPlanModel,
    ResearchSubTaskModel,
)
from app.schemas.research_plan import (
    PlannerOutput,
    ResearchPlanResponse,
    ResearchSubTask,
    SourceType,
)


class SQLiteResearchPlanRepository:
    """
    使用 SQLite 保存研究计划和研究子任务。
    """

    def save(self, plan: ResearchPlanResponse) -> ResearchPlanResponse:
        """
        保存一份新的研究计划及其全部子任务。
        """
        with SessionLocal() as session:
            database_plan = ResearchPlanModel(
                plan_id=str(plan.plan_id),
                task_id=str(plan.task_id),
                plan_title=plan.plan_title,
                overall_strategy=plan.overall_strategy,
                created_at=plan.created_at,
            )
            session.add(database_plan)

            for subtask in plan.subtasks:
                database_subtask = ResearchSubTaskModel(
                    plan_id=str(plan.plan_id),
                    subtask_id=subtask.subtask_id,
                    title=subtask.title,
                    research_question=subtask.research_question,
                    objective=subtask.objective,
                    search_queries=subtask.search_queries,
                    preferred_source_types=[
                        source_type.value
                        for source_type in subtask.preferred_source_types
                    ],
                    priority=subtask.priority,
                )
                session.add(database_subtask)

            session.commit()

        return plan

    def get_by_task_id(self, task_id: UUID) -> ResearchPlanResponse | None:
        """
        查询一个任务对应的研究计划和全部子任务。
        """
        with SessionLocal() as session:
            plan_statement = select(ResearchPlanModel).where(
                ResearchPlanModel.task_id == str(task_id)
            )
            database_plan = session.scalar(plan_statement)

            if database_plan is None:
                return None

            subtask_statement = (
                select(ResearchSubTaskModel)
                .where(
                    ResearchSubTaskModel.plan_id == database_plan.plan_id
                )
                .order_by(
                    ResearchSubTaskModel.priority.asc(),
                    ResearchSubTaskModel.subtask_id.asc(),
                )
            )
            database_subtasks = session.scalars(subtask_statement).all()

            subtasks = [
                ResearchSubTask(
                    subtask_id=database_subtask.subtask_id,
                    title=database_subtask.title,
                    research_question=database_subtask.research_question,
                    objective=database_subtask.objective,
                    search_queries=database_subtask.search_queries,
                    preferred_source_types=[
                        SourceType(source_type)
                        for source_type
                        in database_subtask.preferred_source_types
                    ],
                    priority=database_subtask.priority,
                )
                for database_subtask in database_subtasks
            ]

            return ResearchPlanResponse(
                plan_id=UUID(database_plan.plan_id),
                task_id=UUID(database_plan.task_id),
                plan_title=database_plan.plan_title,
                overall_strategy=database_plan.overall_strategy,
                subtasks=subtasks,
                created_at=database_plan.created_at,
            )