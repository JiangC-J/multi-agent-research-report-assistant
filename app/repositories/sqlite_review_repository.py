from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.review import ClaimReviewModel
from app.schemas.review import (
    ClaimReviewResponse,
    EvidenceAssessment,
    ReviewDecision,
    ReviewIssue,
)


class SQLiteReviewRepository:
    """
    使用 SQLite 保存和查询审核记录。
    """

    def create(
        self,
        review: ClaimReviewResponse,
    ) -> ClaimReviewResponse:
        """
        创建一条新的审核记录。
        """
        with SessionLocal() as session:
            database_review = ClaimReviewModel(
                review_id=str(review.review_id),
                task_id=str(review.task_id),
                claim_id=str(review.claim_id),
                decision=review.decision.value,
                evidence_assessment=review.evidence_assessment.value,
                verified_evidence_ids=[
                    str(evidence_id)
                    for evidence_id in review.verified_evidence_ids
                ],
                review_comment=review.review_comment,
                issues=[
                    issue.model_dump(mode="json")
                    for issue in review.issues
                ],
                required_actions=review.required_actions,
                reviewed_at=review.reviewed_at,
            )
            session.add(database_review)
            session.commit()

        return review

    def list_by_claim_id(
        self,
        claim_id: UUID,
    ) -> list[ClaimReviewResponse]:
        """
        查询一条 Claim 的审核历史。
        """
        with SessionLocal() as session:
            statement = (
                select(ClaimReviewModel)
                .where(ClaimReviewModel.claim_id == str(claim_id))
                .order_by(ClaimReviewModel.reviewed_at.asc())
            )
            database_reviews = session.scalars(statement).all()

            return [
                self._to_schema(database_review)
                for database_review in database_reviews
            ]

    @staticmethod
    def _to_schema(
        database_review: ClaimReviewModel,
    ) -> ClaimReviewResponse:
        """
        将数据库模型转换为 API Schema。
        """
        return ClaimReviewResponse(
            review_id=UUID(database_review.review_id),
            task_id=UUID(database_review.task_id),
            claim_id=UUID(database_review.claim_id),
            decision=ReviewDecision(database_review.decision),
            evidence_assessment=EvidenceAssessment(
                database_review.evidence_assessment
            ),
            verified_evidence_ids=[
                UUID(evidence_id)
                for evidence_id in database_review.verified_evidence_ids
            ],
            review_comment=database_review.review_comment,
            issues=[
                ReviewIssue.model_validate(issue)
                for issue in database_review.issues
            ],
            required_actions=database_review.required_actions,
            reviewed_at=database_review.reviewed_at,
        )