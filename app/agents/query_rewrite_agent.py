from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts.researcher import (
    QUERY_REWRITE_SYSTEM_PROMPT,
    build_query_rewrite_user_prompt,
)
from app.schemas.research_plan import ResearchSubTask
from app.schemas.research_query import QueryRewriteOutput


@dataclass(frozen=True)
class QueryRewriteAgentResult:
    """
    Query Rewrite Agent 的结果及模型使用指标。
    """

    query_output: QueryRewriteOutput
    input_tokens: int
    output_tokens: int


class QueryRewriteAgent:
    """
    将 Planner 的初始查询改写为更适合检索的查询集合。
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def rewrite_queries(
        self,
        subtask: ResearchSubTask,
        report_language: str,
    ) -> QueryRewriteAgentResult:
        """
        调用模型生成结构化改写查询。
        """
        structured_llm = self._llm.with_structured_output(
            QueryRewriteOutput,
            method="json_mode",
            include_raw=True,
        )

        messages = [
            SystemMessage(content=QUERY_REWRITE_SYSTEM_PROMPT),
            HumanMessage(
                content=build_query_rewrite_user_prompt(
                    subtask_title=subtask.title,
                    research_question=subtask.research_question,
                    objective=subtask.objective,
                    original_queries=subtask.search_queries,
                    preferred_source_types=[
                        source_type.value
                        for source_type
                        in subtask.preferred_source_types
                    ],
                    report_language=report_language,
                )
            ),
        ]

        result = await structured_llm.ainvoke(messages)

        parsing_error = result["parsing_error"]

        if parsing_error is not None:
            raise RuntimeError(
                "Query Rewrite 结构化输出解析失败："
                f"{parsing_error}"
            )

        parsed_output = result["parsed"]

        if isinstance(parsed_output, QueryRewriteOutput):
            query_output = parsed_output
        else:
            query_output = QueryRewriteOutput.model_validate(
                parsed_output
            )

        raw_response = result["raw"]
        usage_metadata = raw_response.usage_metadata or {}

        return QueryRewriteAgentResult(
            query_output=query_output,
            input_tokens=int(
                usage_metadata.get("input_tokens", 0)
            ),
            output_tokens=int(
                usage_metadata.get("output_tokens", 0)
            ),
        )
