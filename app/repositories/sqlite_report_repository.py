from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.report import ReportModel
from app.schemas.report import (
    ReportCitationDraft,
    ReportResponse,
    ReportSectionDraft,
    ReportStatus,
)


class SQLiteReportRepository:
    """
    使用 SQLite 保存和查询研究报告。
    """

    def create(self, report: ReportResponse) -> ReportResponse:
        """
        创建一份新的报告。
        """
        with SessionLocal() as session:
            database_report = ReportModel(
                report_id=str(report.report_id),
                task_id=str(report.task_id),
                status=report.status.value,
                report_title=report.report_title,
                sections=[
                    section.model_dump(mode="json")
                    for section in report.sections
                ],
                citations=[
                    citation.model_dump(mode="json")
                    for citation in report.citations
                ],
                markdown_content=report.markdown_content,
                created_at=report.created_at,
            )
            session.add(database_report)
            session.commit()

        return report

    def get_by_task_id(self, task_id: UUID) -> ReportResponse | None:
        """
        查询一个任务的最终报告。
        """
        with SessionLocal() as session:
            statement = select(ReportModel).where(
                ReportModel.task_id == str(task_id)
            )
            database_report = session.scalar(statement)

            if database_report is None:
                return None

            return ReportResponse(
                report_id=UUID(database_report.report_id),
                task_id=UUID(database_report.task_id),
                status=ReportStatus(database_report.status),
                report_title=database_report.report_title,
                sections=[
                    ReportSectionDraft.model_validate(section)
                    for section in database_report.sections
                ],
                citations=[
                    ReportCitationDraft.model_validate(citation)
                    for citation in database_report.citations
                ],
                markdown_content=database_report.markdown_content,
                created_at=database_report.created_at,
            )