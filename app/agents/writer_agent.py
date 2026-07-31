from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts.writer import (
    WRITER_SYSTEM_PROMPT,
    build_writer_user_prompt,
)
from app.schemas.claim import ClaimResponse
from app.schemas.evidence import EvidenceResponse
from app.schemas.report import ReportDraft


@dataclass(frozen=True)
class WriterAgentResult:
    """
    Writer Agent 的结果及模型使用指标。
    """

    report_draft: ReportDraft
    input_tokens: int
    output_tokens: int


class WriterAgent:
    """
    将 APPROVED Claim 组织为结构化报告的 Agent。
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def write_report(
        self,
        research_topic: str,
        requirements: str | None,
        approved_claims: list[ClaimResponse],
        evidences_by_id: dict,
    ) -> WriterAgentResult:
        """
        调用模型生成结构化 ReportDraft。
        """
        structured_llm = self._llm.with_structured_output(
            ReportDraft,
            method="json_mode",
            include_raw=True,
        )

        messages = [
            SystemMessage(content=WRITER_SYSTEM_PROMPT),
            HumanMessage(
                content=build_writer_user_prompt(
                    research_topic=research_topic,
                    requirements=requirements,
                    approved_claims=approved_claims,
                    evidences_by_id=evidences_by_id,
                )
            ),
        ]

        result = await structured_llm.ainvoke(messages)

        parsing_error = result["parsing_error"]

        if parsing_error is not None:
            raise RuntimeError(
                "Writer 结构化输出解析失败："
                f"{parsing_error}"
            )

        parsed_output = result["parsed"]

        if isinstance(parsed_output, ReportDraft):
            report_draft = parsed_output
        else:
            report_draft = ReportDraft.model_validate(parsed_output)

        raw_response = result["raw"]
        usage_metadata = raw_response.usage_metadata or {}

        return WriterAgentResult(
            report_draft=report_draft,
            input_tokens=int(
                usage_metadata.get("input_tokens", 0)
            ),
            output_tokens=int(
                usage_metadata.get("output_tokens", 0)
            ),
        )
