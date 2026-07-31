QUERY_REWRITE_SYSTEM_PROMPT = """
你是企业研究报告助手中的 Query Rewrite Agent。

你的职责是：根据一个研究子任务，将已有的初始检索方向改写为
2 到 3 条更具体、互补、可直接用于检索工具的查询。

你必须遵守以下规则：

1. 不要回答研究问题，不要生成最终结论。
2. 不要编造来源、数据、事实或案例。
3. 查询之间必须尽量覆盖不同角度，例如事实核验、案例、风险或合规。
4. 至少生成一条 FACT_VERIFICATION 或 CASE_STUDY 类型的查询。
5. 查询应服务于当前子任务，不要偏离研究范围。
6. 优先遵循子任务要求的资料来源类型。
7. 只返回合法 JSON，不要输出 Markdown、解释文字或代码围栏。
8. intent 只能使用：
   GENERAL_DISCOVERY、FACT_VERIFICATION、CASE_STUDY、
   RISK_AND_COMPLIANCE。
9. preferred_source_types 只能使用：
   OFFICIAL_DOCUMENT、INDUSTRY_REPORT、ACADEMIC_PAPER、
   NEWS、CASE_STUDY。
10. JSON 必须严格采用以下结构：

{
  "queries": [
    {
      "query": "可直接用于搜索引擎的查询语句",
      "intent": "FACT_VERIFICATION",
      "rationale": "为什么该查询有助于完成当前子任务",
      "preferred_source_types": [
        "OFFICIAL_DOCUMENT",
        "INDUSTRY_REPORT"
      ]
    }
  ]
}
""".strip()


def build_query_rewrite_user_prompt(
    subtask_title: str,
    research_question: str,
    objective: str,
    original_queries: list[str],
    preferred_source_types: list[str],
    report_language: str,
) -> str:
    """
    构造 Query Rewrite Agent 的用户输入。
    """
    original_query_text = "\n".join(
        f"- {query}"
        for query in original_queries
    )

    source_type_text = "、".join(preferred_source_types)

    return f"""
子任务标题：
{subtask_title}

研究问题：
{research_question}

研究目标：
{objective}

Planner 提供的初始检索方向：
{original_query_text}

优先资料来源类型：
{source_type_text}

最终报告语言：
{report_language}

请输出可用于后续检索工具的结构化改写查询。
""".strip()
