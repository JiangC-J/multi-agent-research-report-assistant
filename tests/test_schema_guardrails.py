from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.claim import ClaimAnalysisOutput
from app.schemas.evidence import EvidenceExtractionOutput
from app.schemas.research_query import QueryRewriteOutput
from app.schemas.review import (
    ClaimReviewDraft,
    EvidenceAssessment,
    ReviewDecision,
)


EVIDENCE_ID_1 = UUID(
    "11111111-1111-1111-1111-111111111111"
)
EVIDENCE_ID_2 = UUID(
    "22222222-2222-2222-2222-222222222222"
)


def build_query_payload(
    intent: str = "FACT_VERIFICATION",
) -> dict:
    """
    构造一条 Query Rewrite 测试数据。
    """
    return {
        "queries": [
            {
                "query": (
                    "2025 enterprise AI Agent "
                    "deployment risk analysis"
                ),
                "intent": intent,
                "rationale": (
                    "用于核验企业部署 AI Agent 时的"
                    "数据安全、治理和合规风险。"
                ),
                "preferred_source_types": [
                    "OFFICIAL_DOCUMENT",
                    "ACADEMIC_PAPER",
                ],
            }
        ]
    }


def build_evidence_candidate(
    source_url: str,
    evidence_kind: str = "FACT",
) -> dict:
    """
    构造一条 Evidence Extraction 测试数据。
    """
    return {
        "source_url": source_url,
        "source_type": "OFFICIAL_DOCUMENT",
        "evidence_kind": evidence_kind,
        "evidence_summary": (
            "该来源说明了企业部署 AI Agent 时"
            "需要关注的治理和安全要求。"
        ),
        "relevance_score": 0.9,
        "source_quality_hint": "HIGH",
    }


def build_claim_payload(
    index: int,
) -> dict:
    """
    构造一条 Analyst Claim 测试数据。
    """
    return {
        "claim_text": (
            f"研究结论 {index}：企业部署 AI Agent 时"
            "需要建立明确的治理和人工监督机制。"
        ),
        "claim_type": "RECOMMENDATION",
        "evidence_ids": [
            str(EVIDENCE_ID_1),
        ],
        "evidence_rationale": (
            "该 Evidence 说明了企业 AI Agent "
            "治理、监督和风险控制的重要性。"
        ),
        "confidence_score": 0.8,
        "limitations": (
            "该结论仅适用于当前 Evidence "
            "所覆盖的企业应用范围。"
        ),
    }


def test_single_valid_query_is_accepted() -> None:
    """
    即使模型只返回一条合法查询，
    系统也应允许降级为单查询检索。
    """
    output = QueryRewriteOutput.model_validate(
        build_query_payload()
    )

    assert len(output.queries) == 1
    assert (
        output.queries[0].intent.value
        == "FACT_VERIFICATION"
    )


def test_source_type_in_intent_is_normalized() -> None:
    """
    模型把 ACADEMIC_PAPER 错填到 intent 时，
    系统应将其归一化为 FACT_VERIFICATION。
    """
    output = QueryRewriteOutput.model_validate(
        build_query_payload(
            intent="ACADEMIC_PAPER",
        )
    )

    assert (
        output.queries[0].intent.value
        == "FACT_VERIFICATION"
    )


def test_evidence_kind_alias_is_normalized() -> None:
    """
    模型返回 GUIDELINE 时，
    系统应将其归一化为 BEST_PRACTICE。
    """
    output = EvidenceExtractionOutput.model_validate(
        {
            "evidences": [
                build_evidence_candidate(
                    source_url=(
                        "https://example.com/"
                        "ai-agent-guideline"
                    ),
                    evidence_kind="GUIDELINE",
                )
            ]
        }
    )

    assert (
        output.evidences[0].evidence_kind.value
        == "BEST_PRACTICE"
    )


def test_invalid_model_source_type_is_ignored() -> None:
    """
    source_type 已由服务端负责。

    即使模型仍沿用旧格式，并把 BEST_PRACTICE
    错写到 source_type，Evidence Extraction 输出
    也不能因此解析失败。
    """
    candidate = build_evidence_candidate(
        source_url=(
            "https://example.com/"
            "ai-agent-best-practice"
        ),
        evidence_kind="BEST_PRACTICE",
    )

    candidate["source_type"] = "BEST_PRACTICE"

    output = EvidenceExtractionOutput.model_validate(
        {
            "evidences": [candidate],
        }
    )

    assert len(output.evidences) == 1
    assert (
        output.evidences[0].evidence_kind.value
        == "BEST_PRACTICE"
    )

def test_duplicate_evidence_urls_are_deduplicated() -> None:
    """
    同一轮 Evidence Extraction 中，
    相同 URL 最多保留一次。
    """
    source_url = (
        "https://example.com/"
        "enterprise-ai-governance"
    )

    output = EvidenceExtractionOutput.model_validate(
        {
            "evidences": [
                build_evidence_candidate(
                    source_url=source_url,
                ),
                build_evidence_candidate(
                    source_url=source_url,
                ),
            ]
        }
    )

    assert len(output.evidences) == 1
    assert str(output.evidences[0].source_url).rstrip(
        "/"
    ) == source_url


def test_inconsistent_approved_review_is_downgraded() -> None:
    """
    APPROVED 与 INSUFFICIENT 相互矛盾时，
    系统必须保守降级为 NEEDS_REVISION。
    """
    review = ClaimReviewDraft.model_validate(
        {
            "decision": "APPROVED",
            "evidence_assessment": "INSUFFICIENT",
            "verified_evidence_ids": [
                str(EVIDENCE_ID_1),
            ],
            "review_comment": (
                "当前审核结果认为证据不足，"
                "无法完全支持这条研究结论。"
            ),
            "issues": [],
            "required_actions": [],
        }
    )

    assert (
        review.decision
        == ReviewDecision.NEEDS_REVISION
    )
    assert (
        review.evidence_assessment
        == EvidenceAssessment.INSUFFICIENT
    )
    assert len(review.issues) >= 1
    assert len(review.required_actions) >= 1


def test_more_than_three_claims_are_rejected() -> None:
    """
    Analyst 一次生成超过三条 Claim 时，
    Schema 必须拒绝，避免输出无限膨胀。
    """
    payload = {
        "claims": [
            build_claim_payload(index)
            for index in range(1, 5)
        ]
    }

    with pytest.raises(ValidationError):
        ClaimAnalysisOutput.model_validate(payload)