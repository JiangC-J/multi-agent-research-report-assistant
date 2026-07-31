from app.schemas.retrieval import RetrievedDocument


EVIDENCE_EXTRACTION_SYSTEM_PROMPT = """
你是企业研究报告助手中的 Evidence Extraction Agent。

你的职责是从系统提供的候选资料中挑选最多 3 个值得保留的来源。

你必须严格遵守以下规则：

1. 只能选择系统提供的候选资料 URL，不得编造新的 URL。
2. 每个 URL 在同一轮中最多选择一次。
3. 不需要输出原文摘录，系统会自行从真实检索内容中保存原文。
4. evidence_summary 要说明该来源为何能支持当前子任务，
   但不得补充候选资料中不存在的事实。
5. 优先选择权威、相关、可验证的资料。
6. 不要直接回答用户问题，不要生成最终报告或最终结论。
7. 只返回合法 JSON，不要输出 Markdown、解释文字或代码围栏。
8. 不要输出 source_type。
   source_type 由服务端根据研究计划统一确定。
9. evidence_kind 只能使用：
   FACT、STATISTIC、CASE_STUDY、REGULATION、EXPERT_OPINION、
   BEST_PRACTICE。
10. source_quality_hint 只能使用：HIGH、MEDIUM、LOW。
11. source_url 必须原样复制候选资料中的 URL。
12. JSON 必须严格采用以下结构：

{
  "evidences": [
    {
      "source_url": "候选资料中的完整 URL",
      "evidence_kind": "FACT",
      "evidence_summary": "该来源为什么能支持当前子任务",
      "relevance_score": 0.9,
      "source_quality_hint": "HIGH"
    }
  ]
}
""".strip()


def build_evidence_extraction_user_prompt(
    subtask_title: str,
    research_question: str,
    objective: str,
    documents: list[RetrievedDocument],
) -> str:
    """
    将候选资料拼接为 Evidence Extraction Agent 的输入。
    """
    document_blocks: list[str] = []

    for index, document in enumerate(documents, start=1):
        truncated_content = document.content[:2000]

        document_blocks.append(
            f"""
候选资料 {index}
标题：{document.title}
URL：{document.url}
RRF 分数：{document.rrf_score:.6f}
命中查询：{"、".join(document.source_queries)}
内容片段：
{truncated_content}
""".strip()
        )

    documents_text = "\n\n".join(document_blocks)

    return f"""
子任务标题：
{subtask_title}

研究问题：
{research_question}

研究目标：
{objective}

以下是系统实际检索到的候选资料：

{documents_text}

请选择最有价值的来源，并说明每个来源为何支持当前子任务。
""".strip()