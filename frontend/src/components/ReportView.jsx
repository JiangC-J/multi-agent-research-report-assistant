const SECTION_LABELS = {
  EXECUTIVE_SUMMARY: '执行摘要',
  KEY_FINDINGS: '核心发现',
  RISKS: '风险与限制',
  RECOMMENDATIONS: '落地建议',
  LIMITATIONS: '研究局限',
}

function getSourceDomain(sourceUrl) {
  try {
    return new URL(sourceUrl).hostname
  } catch {
    return sourceUrl
  }
}

function ReportView({ report, evidences }) {
  const evidenceById = new Map(
    evidences.map((evidence) => [evidence.evidence_id, evidence]),
  )

  return (
    <section className="report-view">
      <div className="report-view-header">
        <div>
          <p className="eyebrow">FINAL RESEARCH REPORT</p>
          <h2>{report.report_title}</h2>
        </div>

        <span className="report-status">{report.status}</span>
      </div>

      <div className="report-layout">
        <article className="report-article">
          {report.sections.map((section, index) => (
            <section className="report-section" key={section.section_type}>
              <span className="report-section-index">
                {String(index + 1).padStart(2, '0')}
              </span>

              <div>
                <p className="report-section-type">
                  {SECTION_LABELS[section.section_type] ?? section.section_type}
                </p>
                <h3>{section.heading}</h3>
                <p className="report-section-content">{section.content}</p>
              </div>
            </section>
          ))}
        </article>

        <aside className="source-panel">
          <p className="eyebrow">SOURCES</p>
          <h3>引用来源</h3>

          <ol className="source-list">
            {report.citations.map((citation, index) => {
              const evidence = evidenceById.get(citation.evidence_id)

              return (
                <li key={citation.citation_key}>
                  <span className="source-number">{index + 1}</span>

                  <div>
                    <p className="source-type">
                      {evidence?.source_type ?? 'SOURCE'}
                    </p>

                    {evidence ? (
                      <a
                        href={evidence.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {evidence.source_title}
                      </a>
                    ) : (
                      <p className="missing-source">
                        该引用的来源详情暂不可用
                      </p>
                    )}

                    {evidence && (
                      <p className="source-domain">
                        {getSourceDomain(evidence.source_url)}
                      </p>
                    )}
                  </div>
                </li>
              )
            })}
          </ol>
        </aside>
      </div>
    </section>
  )
}

export default ReportView