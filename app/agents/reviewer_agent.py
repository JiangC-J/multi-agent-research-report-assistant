from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts.reviewer import (
    REVIEWER_SYSTEM_PROMPT,
    build_reviewer_user_prompt,
)
from app.schemas.claim import ClaimResponse
from app.schemas.evidence import EvidenceResponse
from app.schemas.review import ClaimReviewDraft


@dataclass(frozen=True)
class ReviewerAgentResult:
    """
    Reviewer Agent 的结果及模型使用指标。
    """

    review_draft: ClaimReviewDraft
    input_tokens: int
    output_tokens: int


class ReviewerAgent:
    """
    审核 Claim 与 Evidence 一致性的 Agent。
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def review_claim(
        self,
        claim: ClaimResponse,
        evidences: list[EvidenceResponse],
    ) -> ReviewerAgentResult:
        """
        调用模型审核一条 Claim。
        """
        structured_llm = self._llm.with_structured_output(
            ClaimReviewDraft,
            method="json_mode",
            include_raw=True,
        )

        messages = [
            SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
            HumanMessage(
                content=build_reviewer_user_prompt(
                    claim=claim,
                    evidences=evidences,
                )
            ),
        ]

        result = await structured_llm.ainvoke(messages)

        parsing_error = result["parsing_error"]

        if parsing_error is not None:
            raise RuntimeError(
                "Reviewer 结构化输出解析失败："
                f"{parsing_error}"
            )

        parsed_output = result["parsed"]

        if isinstance(parsed_output, ClaimReviewDraft):
            review_draft = parsed_output
        else:
            review_draft = ClaimReviewDraft.model_validate(
                parsed_output
            )

        raw_response = result["raw"]
        usage_metadata = raw_response.usage_metadata or {}

        return ReviewerAgentResult(
            review_draft=review_draft,
            input_tokens=int(
                usage_metadata.get("input_tokens", 0)
            ),
            output_tokens=int(
                usage_metadata.get("output_tokens", 0)
            ),
        )
