from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts.planner import (
    PLANNER_SYSTEM_PROMPT,
    build_planner_user_prompt,
)
from app.schemas.research_plan import PlannerOutput


@dataclass(frozen=True)
class PlannerAgentResult:
    """
    Planner Agent 的执行结果及模型使用指标。
    """

    plan: PlannerOutput
    input_tokens: int
    output_tokens: int


class PlannerAgent:
    """
    将研究主题拆分为结构化子任务的 Agent。
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def create_plan(
        self,
        research_topic: str,
        requirements: str | None,
        report_language: str,
    ) -> PlannerAgentResult:
        """
        调用模型生成并校验结构化研究计划。
        """
        structured_llm = self._llm.with_structured_output(
            PlannerOutput,
            method="json_mode",
            include_raw=True,
        )

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(
                content=build_planner_user_prompt(
                    research_topic=research_topic,
                    requirements=requirements,
                    report_language=report_language,
                )
            ),
        ]

        result = await structured_llm.ainvoke(messages)

        parsing_error = result["parsing_error"]

        if parsing_error is not None:
            raise RuntimeError(
                "Planner 结构化输出解析失败："
                f"{parsing_error}"
            )

        parsed_output = result["parsed"]

        if isinstance(parsed_output, PlannerOutput):
            plan = parsed_output
        else:
            plan = PlannerOutput.model_validate(parsed_output)

        raw_response = result["raw"]
        usage_metadata = raw_response.usage_metadata or {}

        return PlannerAgentResult(
            plan=plan,
            input_tokens=int(
                usage_metadata.get("input_tokens", 0)
            ),
            output_tokens=int(
                usage_metadata.get("output_tokens", 0)
            ),
        )
