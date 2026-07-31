from uuid import UUID

from app.schemas.evidence import EvidenceResponse
from app.schemas.report import ReportDraft


def render_markdown_report(
    report: ReportDraft,
    evidences_by_id: dict[UUID, EvidenceResponse],
) -> str:
    """
    将结构化报告内容渲染为 Markdown。
    """
    lines = [
        f"# {report.report_title}",
        "",
    ]

    for section in report.sections:
        section_claim_ids = set(section.claim_ids)

        related_citation_keys = [
            citation.citation_key
            for citation in report.citations
            if section_claim_ids.intersection(citation.claim_ids)
        ]

        lines.extend(
            [
                f"## {section.heading}",
                "",
                section.content,
                "",
            ]
        )

        if related_citation_keys:
            citation_markers = "、".join(
                f"[{citation_key}]"
                for citation_key in related_citation_keys
            )
            lines.extend(
                [
                    f"参考来源：{citation_markers}",
                    "",
                ]
            )

    lines.extend(
        [
            "## 来源",
            "",
        ]
    )

    for citation in report.citations:
        evidence = evidences_by_id[citation.evidence_id]

        lines.append(
            f"- [{citation.citation_key}] "
            f"{evidence.source_title}：{evidence.source_url}"
        )

    return "\n".join(lines)