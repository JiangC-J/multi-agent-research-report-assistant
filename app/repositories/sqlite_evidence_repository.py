from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.evidence import EvidenceModel
from app.schemas.evidence import (
    EvidenceKind,
    EvidenceResponse,
    SourceQualityHint,
)
from app.schemas.research_plan import SourceType


class SQLiteEvidenceRepository:
    """
    使用 SQLite 保存和查询证据。
    """

    def create(self, evidence: EvidenceResponse) -> EvidenceResponse:
        """
        创建一条新的证据记录。
        """
        with SessionLocal() as session:
            database_evidence = EvidenceModel(
                evidence_id=str(evidence.evidence_id),
                task_id=str(evidence.task_id),
                subtask_id=evidence.subtask_id,
                source_title=evidence.source_title,
                source_url=str(evidence.source_url),
                source_type=evidence.source_type.value,
                published_at=evidence.published_at,
                evidence_kind=evidence.evidence_kind.value,
                content_excerpt=evidence.content_excerpt,
                evidence_summary=evidence.evidence_summary,
                relevance_score=evidence.relevance_score,
                source_quality_hint=evidence.source_quality_hint.value,
                created_at=evidence.created_at,
            )
            session.add(database_evidence)
            session.commit()

        return evidence

    def exists_by_task_subtask_and_url(
        self,
        task_id: UUID,
        subtask_id: str,
        source_url: str,
    ) -> bool:
        """
        检查同一子任务中是否已保存相同来源。
        """
        with SessionLocal() as session:
            statement = select(EvidenceModel.evidence_id).where(
                EvidenceModel.task_id == str(task_id),
                EvidenceModel.subtask_id == subtask_id,
                EvidenceModel.source_url == source_url,
            )

            return session.scalar(statement) is not None

    def list_by_task_id(self, task_id: UUID) -> list[EvidenceResponse]:
        """
        查询任务的全部证据。

        先按子任务，再按相关性降序排列。
        """
        with SessionLocal() as session:
            statement = (
                select(EvidenceModel)
                .where(EvidenceModel.task_id == str(task_id))
                .order_by(
                    EvidenceModel.subtask_id.asc(),
                    EvidenceModel.relevance_score.desc(),
                )
            )
            database_evidences = session.scalars(statement).all()

            return [
                self._to_schema(database_evidence)
                for database_evidence in database_evidences
            ]

    @staticmethod
    def _to_schema(database_evidence: EvidenceModel) -> EvidenceResponse:
        """
        将数据库模型转换为 API Schema。
        """
        return EvidenceResponse(
            evidence_id=UUID(database_evidence.evidence_id),
            task_id=UUID(database_evidence.task_id),
            subtask_id=database_evidence.subtask_id,
            source_title=database_evidence.source_title,
            source_url=database_evidence.source_url,
            source_type=SourceType(database_evidence.source_type),
            published_at=database_evidence.published_at,
            evidence_kind=EvidenceKind(database_evidence.evidence_kind),
            content_excerpt=database_evidence.content_excerpt,
            evidence_summary=database_evidence.evidence_summary,
            relevance_score=database_evidence.relevance_score,
            source_quality_hint=SourceQualityHint(
                database_evidence.source_quality_hint
            ),
            created_at=database_evidence.created_at,
        )