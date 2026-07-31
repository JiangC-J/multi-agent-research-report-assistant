from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts.evidence_extraction import (
    EVIDENCE_EXTRACTION_SYSTEM_PROMPT,
    build_evidence_extraction_user_prompt,
)
from app.schemas.evidence import EvidenceExtractionOutput
from app.schemas.research_plan import ResearchSubTask
from app.schemas.retrieval import RetrievedDocument


@dataclass(frozen=True)
class EvidenceExtractionAgentResult:
    """
    Evidence Extraction Agent 的结果及模型使用指标。
    """

    extraction_output: EvidenceExtractionOutput
    input_tokens: int
    output_tokens: int


class EvidenceExtractionAgent:
    """
    从候选资料中提取结构化 Evidence 的 Agent。
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def extract_evidences(
        self,
        subtask: ResearchSubTask,
        documents: list[RetrievedDocument],
    ) -> EvidenceExtractionAgentResult:
        """
        调用模型提取可审计的 Evidence 候选。
        """
        structured_llm = self._llm.with_structured_output(
            EvidenceExtractionOutput,
            method="json_mode",
            include_raw=True,
        )

        messages = [
            SystemMessage(content=EVIDENCE_EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(
                content=build_evidence_extraction_user_prompt(
                    subtask_title=subtask.title,
                    research_question=subtask.research_question,
                    objective=subtask.objective,
                    documents=documents,
                )
            ),
        ]

        result = await structured_llm.ainvoke(messages)

        parsing_error = result["parsing_error"]

        if parsing_error is not None:
            raise RuntimeError(
                "Evidence Extraction 结构化输出解析失败："
                f"{parsing_error}"
            )

        parsed_output = result["parsed"]

        if isinstance(parsed_output, EvidenceExtractionOutput):
            extraction_output = parsed_output
        else:
            extraction_output = EvidenceExtractionOutput.model_validate(
                parsed_output
            )

        raw_response = result["raw"]
        usage_metadata = raw_response.usage_metadata or {}

        return EvidenceExtractionAgentResult(
            extraction_output=extraction_output,
            input_tokens=int(
                usage_metadata.get("input_tokens", 0)
            ),
            output_tokens=int(
                usage_metadata.get("output_tokens", 0)
            ),
        )
