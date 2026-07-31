from collections import defaultdict
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.claim import ClaimEvidenceModel, ClaimModel
from app.schemas.claim import (
    ClaimResponse,
    ClaimReviewStatus,
    ClaimType,
)


class SQLiteClaimRepository:
    """
    使用 SQLite 保存、查询和更新结论。
    """

    def create(self, claim: ClaimResponse) -> ClaimResponse:
        """
        创建一条结论及其 Evidence 关联。
        """
        with SessionLocal() as session:
            database_claim = ClaimModel(
                claim_id=str(claim.claim_id),
                task_id=str(claim.task_id),
                claim_text=claim.claim_text,
                claim_type=claim.claim_type.value,
                evidence_rationale=claim.evidence_rationale,
                confidence_score=claim.confidence_score,
                limitations=claim.limitations,
                review_status=claim.review_status.value,
                review_comment=claim.review_comment,
                created_at=claim.created_at,
            )
            session.add(database_claim)

            for evidence_id in claim.evidence_ids:
                evidence_relation = ClaimEvidenceModel(
                    claim_id=str(claim.claim_id),
                    evidence_id=str(evidence_id),
                )
                session.add(evidence_relation)

            session.commit()

        return claim

    def get_by_id(self, claim_id: UUID) -> ClaimResponse | None:
        """
        根据 Claim ID 查询结论和关联 Evidence。
        """
        with SessionLocal() as session:
            database_claim = session.get(
                ClaimModel,
                str(claim_id),
            )

            if database_claim is None:
                return None

            evidence_ids = self._get_evidence_ids(
                session,
                database_claim.claim_id,
            )

            return self._to_schema(
                database_claim,
                evidence_ids,
            )

    def update_review_status(
        self,
        claim_id: UUID,
        review_status: ClaimReviewStatus,
        review_comment: str,
    ) -> ClaimResponse | None:
        """
        更新结论当前审核状态和审核意见。
        """
        with SessionLocal() as session:
            database_claim = session.get(
                ClaimModel,
                str(claim_id),
            )

            if database_claim is None:
                return None

            database_claim.review_status = review_status.value
            database_claim.review_comment = review_comment

            session.commit()

            evidence_ids = self._get_evidence_ids(
                session,
                database_claim.claim_id,
            )

            return self._to_schema(
                database_claim,
                evidence_ids,
            )

    def list_by_task_id(self, task_id: UUID) -> list[ClaimResponse]:
        """
        查询一个任务的全部结论及其关联 Evidence。
        """
        with SessionLocal() as session:
            claim_statement = (
                select(ClaimModel)
                .where(ClaimModel.task_id == str(task_id))
                .order_by(ClaimModel.created_at.asc())
            )
            database_claims = session.scalars(claim_statement).all()

            if not database_claims:
                return []

            claim_ids = [
                database_claim.claim_id
                for database_claim in database_claims
            ]

            relation_statement = select(ClaimEvidenceModel).where(
                ClaimEvidenceModel.claim_id.in_(claim_ids)
            )
            relations = session.scalars(relation_statement).all()

            evidence_ids_by_claim_id: dict[str, list[UUID]] = defaultdict(list)

            for relation in relations:
                evidence_ids_by_claim_id[relation.claim_id].append(
                    UUID(relation.evidence_id)
                )

            return [
                self._to_schema(
                    database_claim,
                    evidence_ids_by_claim_id[database_claim.claim_id],
                )
                for database_claim in database_claims
            ]

    @staticmethod
    def _get_evidence_ids(
        session,
        claim_id: str,
    ) -> list[UUID]:
        """
        查询指定 Claim 绑定的全部 Evidence ID。
        """
        statement = (
            select(ClaimEvidenceModel.evidence_id)
            .where(ClaimEvidenceModel.claim_id == claim_id)
        )

        return [
            UUID(evidence_id)
            for evidence_id in session.scalars(statement).all()
        ]

    @staticmethod
    def _to_schema(
        database_claim: ClaimModel,
        evidence_ids: list[UUID],
    ) -> ClaimResponse:
        """
        将数据库模型转换为 API Schema。
        """
        return ClaimResponse(
            claim_id=UUID(database_claim.claim_id),
            task_id=UUID(database_claim.task_id),
            claim_text=database_claim.claim_text,
            claim_type=ClaimType(database_claim.claim_type),
            evidence_ids=evidence_ids,
            evidence_rationale=database_claim.evidence_rationale,
            confidence_score=database_claim.confidence_score,
            limitations=database_claim.limitations,
            created_at=database_claim.created_at,
            review_status=ClaimReviewStatus(
                database_claim.review_status
            ),
            review_comment=database_claim.review_comment,
        )