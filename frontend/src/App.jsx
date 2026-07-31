import { useEffect, useState } from 'react'
import './App.css'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
const POLLING_INTERVAL_MS = 3000

const INITIAL_FORM = {
  research_topic: '',
  requirements: '',
  report_language: 'zh-CN',
}

const AGENT_STEPS = [
  {
    number: '01',
    name: 'Planner',
    title: '研究规划',
    description: '拆解研究目标，明确范围、问题与交付结构。',
  },
  {
    number: '02',
    name: 'Researcher',
    title: '资料检索',
    description: '检索并提取可靠来源，沉淀可追溯证据。',
  },
  {
    number: '03',
    name: 'Analyst',
    title: '分析归纳',
    description: '将证据转为结构化观点与关键发现。',
  },
  {
    number: '04',
    name: 'Reviewer',
    title: '证据核验',
    description: '检查结论、来源与引用之间的一致性。',
  },
  {
    number: '05',
    name: 'Writer',
    title: '报告成文',
    description: '输出带来源绑定的最终研究报告。',
  },
]

const STATUS_LABELS = {
  PENDING: '等待提交',
  QUEUED: '已进入后台队列',
  PLANNING: '正在规划研究任务',
  RESEARCHING: '正在检索与整理资料',
  ANALYZING: '正在分析证据',
  REVIEWING: '正在审核结论',
  WRITING: '正在生成最终报告',
  COMPLETED: '研究报告已完成',
  FAILED: '任务执行失败',
}

const STATUS_TO_ACTIVE_STEP = {
  PENDING: -1,
  QUEUED: -1,
  PLANNING: 0,
  RESEARCHING: 1,
  ANALYZING: 2,
  REVIEWING: 3,
  WRITING: 4,
  COMPLETED: 5,
  FAILED: -1,
}

const SECTION_LABELS = {
  EXECUTIVE_SUMMARY: '执行摘要',
  KEY_FINDINGS: '核心发现',
  RISKS: '风险与限制',
  RECOMMENDATIONS: '落地建议',
  LIMITATIONS: '研究局限',
}

function getErrorMessage(payload, fallbackMessage) {
  if (typeof payload?.detail === 'string') {
    return payload.detail
  }

  if (typeof payload?.detail === 'object') {
    return JSON.stringify(payload.detail)
  }

  return fallbackMessage
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error(
      getErrorMessage(payload, `请求失败，HTTP 状态码：${response.status}`),
    )
  }

  return payload
}

function getAgentStepState(taskStatus, stepIndex) {
  const activeStepIndex = STATUS_TO_ACTIVE_STEP[taskStatus] ?? -1

  if (taskStatus === 'COMPLETED') {
    return 'completed'
  }

  if (stepIndex < activeStepIndex) {
    return 'completed'
  }

  if (stepIndex === activeStepIndex) {
    return 'active'
  }

  return 'pending'
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

function App() {
  const [formData, setFormData] = useState(INITIAL_FORM)
  const [task, setTask] = useState(null)
  const [submission, setSubmission] = useState(null)
  const [workflowRun, setWorkflowRun] = useState(null)
  const [report, setReport] = useState(null)
  const [evidences, setEvidences] = useState([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [pollingError, setPollingError] = useState('')

  useEffect(() => {
    if (!task?.task_id) {
      return undefined
    }

    let isCancelled = false
    let timerId

    async function pollTaskStatus() {
      try {
        const [latestTask, workflowRuns] = await Promise.all([
          request(`/research-tasks/${task.task_id}`),
          request(`/research-tasks/${task.task_id}/workflow-runs`),
        ])

        if (isCancelled) {
          return
        }

        setTask(latestTask)
        setWorkflowRun(workflowRuns[0] ?? null)
        setPollingError('')

        let shouldContinuePolling = !['COMPLETED', 'FAILED'].includes(
          latestTask.status,
        )

        if (latestTask.status === 'COMPLETED') {
          try {
            const [completedReport, completedEvidences] = await Promise.all([
              request(`/research-tasks/${task.task_id}/report`),
              request(`/research-tasks/${task.task_id}/evidences`),
            ])

            if (isCancelled) {
              return
            }

            setReport(completedReport)
            setEvidences(completedEvidences)
          } catch {
            shouldContinuePolling = true
            setPollingError(
              '任务已完成，正在等待最终报告与引用来源准备完成。',
            )
          }
        }

        if (shouldContinuePolling) {
          timerId = window.setTimeout(pollTaskStatus, POLLING_INTERVAL_MS)
        }
      } catch (error) {
        if (isCancelled) {
          return
        }

        setPollingError(
          error.message || '暂时无法刷新任务状态，将自动重试。',
        )

        timerId = window.setTimeout(pollTaskStatus, POLLING_INTERVAL_MS)
      }
    }

    pollTaskStatus()

    return () => {
      isCancelled = true
      window.clearTimeout(timerId)
    }
  }, [task?.task_id])

  function handleChange(event) {
    const { name, value } = event.target

    setFormData((currentForm) => ({
      ...currentForm,
      [name]: value,
    }))
  }

  async function handleSubmit(event) {
    event.preventDefault()

    setErrorMessage('')
    setPollingError('')
    setTask(null)
    setSubmission(null)
    setWorkflowRun(null)
    setReport(null)
    setEvidences([])
    setIsSubmitting(true)

    try {
      const createdTask = await request('/research-tasks', {
        method: 'POST',
        body: JSON.stringify({
          research_topic: formData.research_topic.trim(),
          requirements: formData.requirements.trim() || null,
          report_language: formData.report_language,
        }),
      })

      setTask(createdTask)

      const workflowSubmission = await request(
        `/research-tasks/${createdTask.task_id}/run`,
        { method: 'POST' },
      )

      setSubmission(workflowSubmission)
    } catch (error) {
      setErrorMessage(error.message || '提交研究任务时发生未知错误。')
    } finally {
      setIsSubmitting(false)
    }
  }

  const taskStatus = task?.status ?? 'PENDING'
  const taskStatusLabel = STATUS_LABELS[taskStatus] ?? taskStatus

  return (
    <div className="research-app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">O</span>
          <div>
            <strong>ORBIT</strong>
            <span>RESEARCH</span>
          </div>
        </div>

        <div className="sidebar-current">
          <span className="sidebar-index">01</span>
          <span>新建研究任务</span>
        </div>

        <div className="sidebar-bottom">
          <span className="system-dot"></span>
          <div>
            <strong>系统已连接</strong>
            <span>Multi-Agent Workspace</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="page-header">
          <div>
            <p className="eyebrow">RESEARCH OPERATIONS</p>
            <h1>研究任务</h1>
            <p className="header-description">
              从问题定义到报告交付，由多 Agent 协作完成可追溯的企业研究。
            </p>
          </div>

          <div className="api-indicator">
            <span className="system-dot"></span>
            <span>API 在线</span>
            <span className="api-url">{API_BASE_URL}</span>
          </div>
        </header>

        <div className="content-grid">
          <section className="task-editor">
            <div className="section-heading">
              <div>
                <p className="eyebrow">NEW RESEARCH TASK</p>
                <h2>新建研究任务</h2>
              </div>
              <span className="required-note">带 * 为必填项</span>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="field-group">
                <div className="label-row">
                  <label htmlFor="research_topic">研究主题 *</label>
                  <span>{formData.research_topic.length} / 500</span>
                </div>

                <textarea
                  id="research_topic"
                  name="research_topic"
                  value={formData.research_topic}
                  onChange={handleChange}
                  minLength="10"
                  maxLength="500"
                  rows="6"
                  placeholder="例如：企业在 2025 年部署 AI Agent 的主要价值、风险与落地建议"
                  required
                />
              </div>

              <div className="field-group">
                <div className="label-row">
                  <label htmlFor="requirements">补充要求</label>
                  <span>{formData.requirements.length} / 1000</span>
                </div>

                <textarea
                  id="requirements"
                  name="requirements"
                  value={formData.requirements}
                  onChange={handleChange}
                  maxLength="1000"
                  rows="5"
                  placeholder="例如：面向企业管理者，重点关注成本、数据安全、治理风险和试点建议。"
                />
              </div>

              <div className="field-group language-group">
                <label htmlFor="report_language">报告语言</label>

                <select
                  id="report_language"
                  name="report_language"
                  value={formData.report_language}
                  onChange={handleChange}
                >
                  <option value="zh-CN">中文（简体）</option>
                  <option value="en-US">English</option>
                </select>
              </div>

              <button
                className="submit-button"
                type="submit"
                disabled={isSubmitting}
              >
                <span>{isSubmitting ? '正在投递研究任务…' : '创建并提交任务'}</span>
                <span aria-hidden="true">→</span>
              </button>

              <p className="submit-hint">
                创建后，任务将进入 Celery 后台队列，并由多 Agent 工作流异步执行。
              </p>
            </form>
          </section>

          <aside className="orchestration-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">AGENT ORCHESTRATION</p>
                <h2>协作流程</h2>
              </div>
              <span className="step-count">
                {task ? taskStatusLabel : '5 个阶段'}
              </span>
            </div>

            <ol className="agent-list">
              {AGENT_STEPS.map((agent, index) => (
                <li
                  className={`agent-step agent-step-${getAgentStepState(
                    taskStatus,
                    index,
                  )}`}
                  key={agent.number}
                >
                  <span className="agent-number">{agent.number}</span>
                  <div>
                    <div className="agent-name-row">
                      <strong>{agent.name}</strong>
                      <span>{agent.title}</span>
                    </div>
                    <p>{agent.description}</p>
                  </div>
                </li>
              ))}
            </ol>

            {!task && !errorMessage && (
              <div className="empty-task-state">
                <p className="empty-kicker">准备就绪</p>
                <h3>等待一项研究任务</h3>
                <p>填写左侧研究主题后，执行轨迹与报告结果将在这里展示。</p>
              </div>
            )}

            {errorMessage && (
              <div className="error-state" role="alert">
                <p className="empty-kicker">SUBMISSION FAILED</p>
                <h3>任务没有成功投递</h3>
                <p>{errorMessage}</p>
              </div>
            )}

            {task && (
              <div className="task-result">
                <p className="empty-kicker">LIVE EXECUTION</p>
                <h3>{taskStatusLabel}</h3>
                <p className="result-topic">{task.research_topic}</p>

                {pollingError && (
                  <p className="polling-error">{pollingError}</p>
                )}

                <dl className="metadata-list">
                  <div>
                    <dt>业务状态</dt>
                    <dd>{task.status}</dd>
                  </div>
                  <div>
                    <dt>工作流状态</dt>
                    <dd>{workflowRun?.status ?? '等待 Worker 接收'}</dd>
                  </div>
                  <div>
                    <dt>Task ID</dt>
                    <dd>{task.task_id}</dd>
                  </div>
                  {workflowRun?.duration_ms !== null &&
                    workflowRun?.duration_ms !== undefined && (
                      <div>
                        <dt>执行耗时</dt>
                        <dd>{workflowRun.duration_ms} ms</dd>
                      </div>
                    )}
                  {submission && (
                    <div>
                      <dt>Celery Task ID</dt>
                      <dd>{submission.celery_task_id}</dd>
                    </div>
                  )}
                </dl>
              </div>
            )}
          </aside>
        </div>

        {report && <ReportView report={report} evidences={evidences} />}
      </main>
    </div>
  )
}

export default App