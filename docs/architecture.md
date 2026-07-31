# 企业多 Agent 研究报告助手：系统架构设计

## 1. 架构目标

本系统需要支持一个完整的研究任务生命周期：

1. 用户通过 API 创建研究任务；
2. 系统在后台执行长时间研究流程；
3. 多个 Agent 按职责协作完成任务；
4. 系统保存计划、证据、结论、审核结果和报告；
5. 用户可以查询任务进度、错误信息和最终报告；
6. 系统可以记录耗时、Token 使用量和预估成本。

架构设计遵循以下原则：

- API 请求与长任务执行分离；
- Agent 职责单一；
- Agent 之间传递结构化数据；
- 结论必须关联证据；
- 每个阶段都可以追踪、重试和测试；
- 先使用简单可运行的组件，再逐步升级基础设施。

---

## 2. 整体架构

```mermaid
flowchart TB
    User["用户 / 后期 React 前端"] --> API["FastAPI API"]

    API --> TaskRepo["任务 Repository"]
    TaskRepo --> SQLite["SQLite 数据库"]

    API --> Redis["Redis"]
    API --> Queue["Celery 任务队列"]

    Queue --> Worker["Celery Worker"]
    Worker --> Graph["LangGraph 研究工作流"]

    Graph --> Planner["Planner Agent"]
    Graph --> Researcher["Researcher Agent"]
    Graph --> Analyst["Analyst Agent"]
    Graph --> Reviewer["Reviewer Agent"]
    Graph --> Writer["Writer Agent"]

    Researcher --> Retrieval["检索服务"]
    Retrieval --> QueryRewrite["查询改写"]
    Retrieval --> KeywordSearch["关键词检索"]
    Retrieval --> VectorSearch["向量检索"]
    Retrieval --> Rerank["融合与重排"]

    Graph --> LLM["大模型适配层"]
    Graph --> TaskRepo
    Graph --> Redis