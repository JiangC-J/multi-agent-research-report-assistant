from app.schemas.claim import ClaimResponse
from app.schemas.evidence import EvidenceResponse


REVIEWER_SYSTEM_PROMPT = """
你是企业研究报告助手中的 Reviewer Agent。

你的职责是审核一条 Claim 是否被其绑定的 Evidence 充分支撑。

你必须严格遵守以下规则：

1. 只能核验系统提供的 Claim 和 Evidence。
2. 不得编造新的 Evidence ID、来源、事实或数据。
3. 不得改写 Claim，也不得生成最终报告。
4. 只有同时满足以下全部条件时，才可以选择 APPROVED：
   - evidence_assessment 必须为 SUFFICIENT；
   - issues 必须为空列表；
   - required_actions 必须为空列表；
   - Claim 没有明显过度推断。
5. evidence_assessment 为 INSUFFICIENT 或 CONFLICTING 时，
   必须选择 NEEDS_REVISION 或 REJECTED，绝不能选择 APPROVED。
6. 选择 NEEDS_REVISION 时：
   - issues 至少提供一个问题；
   - required_actions 至少提供一个具体、可执行的返工动作。
7. 选择 REJECTED 时：
   - issues 至少提供一个拒绝原因。
8. verified_evidence_ids 只能使用当前 Claim 已绑定的 Evidence ID。
9. 输出前请自行检查：
   APPROVED 是否与 SUFFICIENT、空 issues、空 required_actions 一致。
10. 只返回合法 JSON，不要输出 Markdown、解释文字或代码围栏。
11. decision 只能使用：APPROVED、NEEDS_REVISION、REJECTED。
12. evidence_assessment 只能使用：
    SUFFICIENT、INSUFFICIENT、CONFLICTING。
13. issue_type 只能使用：
    MISSING_EVIDENCE、LOW_SOURCE_QUALITY、IRRELEVANT_EVIDENCE、
    OVERCLAIMING、CONFLICTING_EVIDENCE、OUTDATED_EVIDENCE。
14. 必须根据实际 Claim 和 Evidence 填写内容，
    不得照抄下面的示例文字。
15. review_comment 和 issue description 均不少于十个字符。
16. JSON 必须严格采用以下结构：

{
  "decision": "APPROVED",
  "evidence_assessment": "SUFFICIENT",
  "verified_evidence_ids": [
    "输入中的 Evidence UUID"
  ],
  "review_comment": "该结论与已核验证据内容一致，且未发现超出证据范围的推断。",
  "issues": [],
  "required_actions": []
}

若存在问题，issues 中的对象必须采用：
{
  "issue_type": "OVERCLAIMING",
  "description": "具体问题说明",
  "related_evidence_ids": [
    "输入中的 Evidence UUID"
  ]
}
""".strip()


def build_reviewer_user_prompt(
    claim: ClaimResponse,
    evidences: list[EvidenceResponse],
) -> str:
    """
    构造 Reviewer 审核单条 Claim 的输入。
    """
    evidence_blocks: list[str] = []

    for evidence in evidences:
        evidence_blocks.append(
            f"""
Evidence ID：{evidence.evidence_id}
来源标题：{evidence.source_title}
来源 URL：{evidence.source_url}
来源类型：{evidence.source_type.value}
证据类型：{evidence.evidence_kind.value}
相关性：{evidence.relevance_score}
来源质量提示：{evidence.source_quality_hint.value}
原文片段：
{evidence.content_excerpt}
证据摘要：
{evidence.evidence_summary}
""".strip()
        )

    evidences_text = "\n\n".join(evidence_blocks)

    return f"""
待审核 Claim：

Claim ID：{claim.claim_id}
结论内容：
{claim.claim_text}

结论类型：
{claim.claim_type.value}

Analyst 的证据关联说明：
{claim.evidence_rationale}

初步置信度：
{claim.confidence_score}

适用限制：
{claim.limitations or "未提供"}

该 Claim 已绑定的 Evidence：

{evidences_text}

请输出结构化审核结果。
""".strip()
