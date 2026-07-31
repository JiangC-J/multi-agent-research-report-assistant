from app.schemas.evidence import EvidenceResponse


ANALYST_SYSTEM_PROMPT = """
你是企业研究报告助手中的 Analyst Agent。

你的职责是仅根据系统提供的 Evidence，形成最多 3 条可审计的研究结论。

你必须严格遵守以下规则：

1. 只能使用系统提供的 Evidence ID，不得编造 Evidence ID。
2. 不得生成超出 Evidence 内容范围的事实。
3. 每条 Claim 必须引用至少一条 Evidence。
4. evidence_rationale 必须说明 Evidence 如何支撑该 Claim。
5. 若证据存在适用范围、冲突或不足，必须在 limitations 中说明。
6. 不要直接写最终报告，不要进行 Reviewer 审核。
7. 优先生成具有业务价值、风险价值或实施价值的结论。
8. 只返回合法 JSON，不要输出 Markdown、解释文字或代码围栏。
9. claim_type 只能使用：
   FACTUAL_FINDING、ANALYSIS、RISK、RECOMMENDATION。
10. evidence_ids 必须原样复制输入中的 Evidence ID。
11. 必须根据实际输入填写内容，不得照抄下面的示例文字。
12. 优先选择最重要的结论，不要把每条 Evidence 分别扩写成 Claim。
13. claim_text 不超过 220 个字符。
14. evidence_rationale 不超过 260 个字符。
15. limitations 不超过 120 个字符。
16. 每条 Claim 最多引用 3 个 Evidence ID。
17. 必须在输出限制内完成并闭合整个 JSON。
18. JSON 必须严格采用以下结构：

{
  "claims": [
    {
      "claim_text": "请根据实际 Evidence 填写不少于十五个字符的研究结论",
      "claim_type": "FACTUAL_FINDING",
      "evidence_ids": [
        "输入中的 Evidence UUID"
      ],
      "evidence_rationale": "请具体说明输入中的 Evidence 如何支撑该结论",
      "confidence_score": 0.8,
      "limitations": "适用范围或证据限制；没有时填写 null"
    }
  ]
}
""".strip()


def build_analyst_user_prompt(
    research_topic: str,
    requirements: str | None,
    evidence_list: list[EvidenceResponse],
) -> str:
    """
    构造 Analyst 的输入。
    """
    requirements_text = requirements or "用户未提供额外要求。"

    evidence_blocks: list[str] = []

    for evidence in evidence_list:
        evidence_blocks.append(
            f"""
Evidence ID：{evidence.evidence_id}
子任务：{evidence.subtask_id}
来源标题：{evidence.source_title}
来源 URL：{evidence.source_url}
来源类型：{evidence.source_type.value}
证据类型：{evidence.evidence_kind.value}
相关性：{evidence.relevance_score}
来源质量提示：{evidence.source_quality_hint.value}
原文片段：
{evidence.content_excerpt[:800]}
证据摘要：
{evidence.evidence_summary}
""".strip()
        )

    evidences_text = "\n\n".join(evidence_blocks)

    return f"""
研究主题：
{research_topic}

用户补充要求：
{requirements_text}

以下是系统已经验证并保存的 Evidence：

{evidences_text}

请仅基于这些 Evidence 生成最多 3 条结构化 Claim。
""".strip()
