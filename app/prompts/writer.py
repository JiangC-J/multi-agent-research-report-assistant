from uuid import UUID

from app.schemas.claim import ClaimResponse
from app.schemas.evidence import EvidenceResponse


WRITER_SYSTEM_PROMPT = """
你是企业研究报告助手中的 Writer Agent。

你的职责是仅根据系统提供的 APPROVED Claim 和其绑定的 Evidence，
生成结构化研究报告草稿。Markdown 将由服务端统一渲染。

你必须严格遵守以下规则：

1. 只能使用输入中的 Claim ID 和 Evidence ID，不得编造 ID。
2. 不得补充输入中不存在的事实、数据、来源或结论。
3. 每个章节必须至少关联一条输入中的 APPROVED Claim。
4. 每条出现在章节中的 Claim，都必须至少有一条 citation。
5. citation 中的 Evidence 必须确实绑定到对应 Claim。
6. sections 至少包含执行摘要和核心发现；可根据证据增加风险、
   建议和局限性章节。
7. 同一种 section_type 最多出现一次。
8. citation_key 必须从 source_1 开始并保持唯一。
9. 只返回合法 JSON，不要输出 Markdown、解释文字或代码围栏。
10. section_type 只能使用：
    EXECUTIVE_SUMMARY、KEY_FINDINGS、RISKS、RECOMMENDATIONS、
    LIMITATIONS。
11. 必须根据实际 Claim 和 Evidence 填写内容，
    不得照抄下面的示例文字。
12. 每个 content 不少于二十个字符。
13. JSON 必须严格采用以下结构：

{
  "report_title": "报告标题",
  "sections": [
    {
      "section_type": "EXECUTIVE_SUMMARY",
      "heading": "执行摘要",
      "content": "请根据实际已审核结论填写不少于二十个字符的章节正文内容。",
      "claim_ids": [
        "输入中的 Claim UUID"
      ]
    },
    {
      "section_type": "KEY_FINDINGS",
      "heading": "核心发现",
      "content": "请根据实际已审核结论填写不少于二十个字符的章节正文内容。",
      "claim_ids": [
        "输入中的 Claim UUID"
      ]
    }
  ],
  "citations": [
    {
      "citation_key": "source_1",
      "evidence_id": "输入中的 Evidence UUID",
      "claim_ids": [
        "该 Evidence 实际支撑的 Claim UUID"
      ]
    }
  ]
}
""".strip()


def build_writer_user_prompt(
    research_topic: str,
    requirements: str | None,
    approved_claims: list[ClaimResponse],
    evidences_by_id: dict[UUID, EvidenceResponse],
) -> str:
    """
    将审核通过的 Claim 及其真实绑定 Evidence 组装为 Writer 输入。

    这里使用当前 Schema 的真实字段名，保证 Agent、Prompt 与
    WriterExecutionService 的接口契约一致。
    """
    requirements_text = requirements or "用户未提供额外要求。"
    claim_blocks: list[str] = []

    for index, claim in enumerate(approved_claims, start=1):
        evidence_blocks: list[str] = []

        for evidence_id in claim.evidence_ids:
            evidence = evidences_by_id.get(evidence_id)

            if evidence is None:
                continue

            evidence_blocks.append(
                f"""
Evidence ID：{evidence.evidence_id}
来源标题：{evidence.source_title}
来源 URL：{evidence.source_url}
来源类型：{evidence.source_type.value}
证据类型：{evidence.evidence_kind.value}
原文片段：
{evidence.content_excerpt}
证据摘要：
{evidence.evidence_summary}
""".strip()
            )

        evidence_text = "\n\n".join(evidence_blocks)

        claim_blocks.append(
            f"""
已审核结论 {index}
Claim ID：{claim.claim_id}
结论类型：{claim.claim_type.value}
结论内容：
{claim.claim_text}
证据关联说明：
{claim.evidence_rationale}
置信度：{claim.confidence_score}
适用限制：{claim.limitations or "未提供"}

该 Claim 实际绑定的 Evidence：
{evidence_text}
""".strip()
        )

    claims_text = "\n\n".join(claim_blocks)

    return f"""
研究主题：
{research_topic}

用户补充要求：
{requirements_text}

以下是允许写入报告的 APPROVED Claim 和绑定 Evidence：

{claims_text}

请生成结构化报告 JSON。所有 ID 必须原样复制。
""".strip()
