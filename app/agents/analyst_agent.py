from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts.analyst import (
    ANALYST_SYSTEM_PROMPT,
    build_analyst_user_prompt,
)
from app.schemas.claim import ClaimAnalysisOutput
from app.schemas.evidence import EvidenceResponse


ANALYST_RETRY_INSTRUCTION = """
上一次输出未通过结构化解析。

请重新生成完整 JSON，并严格执行以下修复要求：
1. 最多输出 3 条 claims。
2. 每条 claim_text 保持精炼。
3. 每条 evidence_rationale 不超过 260 个字符。
4. 每条 limitations 不超过 120 个字符。
5. 只输出 JSON，不要输出任何解释。
6. 必须完整闭合所有字符串、数组和对象。
""".strip()


@dataclass(frozen=True)
class AnalystAgentResult:
    """
    Analyst Agent 的结果及模型使用指标。
    """

    analysis_output: ClaimAnalysisOutput
    input_tokens: int
    output_tokens: int


class AnalystAgent:
    """
    基于 Evidence 生成结构化 Claim 的 Agent。
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def analyze(
        self,
        research_topic: str,
        requirements: str | None,
        evidences: list[EvidenceResponse],
    ) -> AnalystAgentResult:
        """
        调用模型生成结构化结论。
        """
        structured_llm = self._llm.with_structured_output(
            ClaimAnalysisOutput,
            method="json_mode",
            include_raw=True,
        )

        messages = [
            SystemMessage(content=ANALYST_SYSTEM_PROMPT),
            HumanMessage(
                content=build_analyst_user_prompt(
                    research_topic=research_topic,
                    requirements=requirements,
                    evidence_list=evidences,
                )
            ),
        ]

        result = await structured_llm.ainvoke(messages)
        first_usage = self._extract_usage(result)

        parsing_error = result["parsing_error"]

        if parsing_error is not None:
            retry_messages = [
                *messages,
                HumanMessage(content=ANALYST_RETRY_INSTRUCTION),
            ]
            result = await structured_llm.ainvoke(retry_messages)
            retry_parsing_error = result["parsing_error"]

            if retry_parsing_error is not None:
                raise RuntimeError(
                    "Analyst 结构化输出解析失败；"
                    "自动修复重试仍未通过："
                    f"{retry_parsing_error}"
                )

        second_usage = self._extract_usage(result)

        if parsing_error is None:
            total_input_tokens = second_usage[0]
            total_output_tokens = second_usage[1]
        else:
            total_input_tokens = first_usage[0] + second_usage[0]
            total_output_tokens = first_usage[1] + second_usage[1]

        parsed_output = result["parsed"]

        if isinstance(parsed_output, ClaimAnalysisOutput):
            analysis_output = parsed_output
        else:
            analysis_output = ClaimAnalysisOutput.model_validate(
                parsed_output
            )

        return AnalystAgentResult(
            analysis_output=analysis_output,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )

    @staticmethod
    def _extract_usage(result: dict) -> tuple[int, int]:
        """
        从 include_raw=True 的结构化调用结果中读取 token 指标。
        """
        raw_response = result["raw"]
        usage_metadata = raw_response.usage_metadata or {}

        return (
            int(usage_metadata.get("input_tokens", 0)),
            int(usage_metadata.get("output_tokens", 0)),
        )
