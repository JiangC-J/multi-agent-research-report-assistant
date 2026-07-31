import re
from urllib.parse import urldefrag, urlsplit, urlunsplit
from uuid import UUID
from app.schemas.research_plan import SourceType
from app.agents.evidence_extraction_agent import (
    EvidenceExtractionAgent,
)
from app.agents.query_rewrite_agent import QueryRewriteAgent
from app.repositories.research_plan_repository import (
    ResearchPlanRepository,
)
from app.schemas.agent_run import (
    AgentName,
    AgentRunFinish,
    AgentRunStart,
    AgentRunStatus,
)
from app.schemas.evidence import EvidenceDraft
from app.schemas.researcher import ResearcherExecutionResponse
from app.schemas.research_task import TaskStatus, TaskStatusUpdate
from app.schemas.retrieval import RetrievedDocument
from app.services.agent_run_service import AgentRunService
from app.services.evidence_service import (
    DuplicateEvidenceError,
    EvidenceService,
)
from app.services.multi_query_retriever import MultiQueryRetriever
from app.services.research_task_service import (
    ResearchTaskService,
    TaskNotFoundError,
)


class ResearcherTaskStatusMismatchError(Exception):
    """
    任务不处于 RESEARCHING 状态时抛出。
    """


class ResearcherSubTaskNotFoundError(Exception):
    """
    子任务不存在或不属于当前任务时抛出。
    """


class InvalidExtractedEvidenceError(Exception):
    """
    模型提取的 Evidence 不属于候选资料或原文片段未被验证时抛出。
    """


class ResearcherExecutionError(Exception):
    """
    完整 Researcher 流程失败时抛出。
    """


class ResearcherExecutionService:
    """
    Query Rewrite、检索、融合、Evidence Extraction 和保存的编排服务。
    """

    def __init__(
        self,
        task_service: ResearchTaskService,
        plan_repository: ResearchPlanRepository,
        agent_run_service: AgentRunService,
        query_rewrite_agent: QueryRewriteAgent,
        multi_query_retriever: MultiQueryRetriever,
        evidence_extraction_agent: EvidenceExtractionAgent,
        evidence_service: EvidenceService,
    ) -> None:
        self._task_service = task_service
        self._plan_repository = plan_repository
        self._agent_run_service = agent_run_service
        self._query_rewrite_agent = query_rewrite_agent
        self._multi_query_retriever = multi_query_retriever
        self._evidence_extraction_agent = evidence_extraction_agent
        self._evidence_service = evidence_service

    async def research_subtask(
        self,
        task_id: UUID,
        subtask_id: str,
    ) -> ResearcherExecutionResponse:
        """
        为一个子任务完成检索、证据提取和 Evidence 保存。
        """
        task = self._task_service.get_task(task_id)

        if task is None:
            raise TaskNotFoundError("研究任务不存在。")

        if task.status != TaskStatus.RESEARCHING:
            raise ResearcherTaskStatusMismatchError(
                "只有 RESEARCHING 状态的任务可以执行 Researcher；"
                f"当前状态为 {task.status.value}。"
            )

        plan = self._plan_repository.get_by_task_id(task_id)

        if plan is None:
            raise ResearcherSubTaskNotFoundError(
                "当前任务不存在研究计划。"
            )

        subtask = next(
            (
                item
                for item in plan.subtasks
                if item.subtask_id == subtask_id
            ),
            None,
        )

        if subtask is None:
            raise ResearcherSubTaskNotFoundError(
                f"{subtask_id} 不属于当前研究计划。"
            )

        agent_run = self._agent_run_service.start_run(
            task_id=task_id,
            payload=AgentRunStart(
                agent_name=AgentName.RESEARCHER,
                input_summary=(
                    f"为子任务 {subtask_id} 执行查询改写、网页检索、"
                    "RRF 融合和 Evidence 提取。"
                ),
            ),
        )

        try:
            try:
                query_result = (
                    await self._query_rewrite_agent.rewrite_queries(
                        subtask=subtask,
                        report_language=task.report_language.value,
                    )
                )
            except Exception as error:
                raise RuntimeError(
                    f"Query Rewrite 阶段失败：{error}"
                ) from error

            try:
                documents, failed_queries = (
                    await self._multi_query_retriever.retrieve(
                        queries=query_result.query_output.queries,
                    )
                )
            except Exception as error:
                raise RuntimeError(
                    f"网页检索阶段失败：{error}"
                ) from error

            if not documents:
                raise RuntimeError("所有检索查询均未返回可用资料。")

            try:
                extraction_result = (
                    await self._evidence_extraction_agent.extract_evidences(
                        subtask=subtask,
                        documents=documents[:6],
                    )
                )
            except Exception as error:
                raise RuntimeError(
                    f"Evidence Extraction 阶段失败：{error}"
                ) from error

            evidence_drafts = self._build_validated_evidence_drafts(
                extraction_candidates=(
                    extraction_result.extraction_output.evidences
                ),
                documents=documents,
                source_type=subtask.preferred_source_types[0],
            )

            saved_evidences = []
            skipped_duplicate_source_urls = []

            for evidence_draft in evidence_drafts:
                try:
                    saved_evidence = self._evidence_service.create_evidence(
                        task_id=task_id,
                        subtask_id=subtask_id,
                        payload=evidence_draft,
                    )
                    saved_evidences.append(saved_evidence)
                except DuplicateEvidenceError:
                    skipped_duplicate_source_urls.append(
                        evidence_draft.source_url
                    )

            if not saved_evidences:
                raise RuntimeError(
                    "没有保存新的 Evidence，候选来源可能全部重复。"
                )
        except Exception as error:
            error_message = str(error)[:2000]

            self._safe_finish_failed_run(
                run_id=agent_run.run_id,
                error_message=error_message,
            )
            self._safe_mark_task_failed(
                task_id=task_id,
                error_message=error_message,
            )

            raise ResearcherExecutionError(
                "Researcher 执行失败："
                f"{error_message}"
            ) from error

        total_input_tokens = (
            query_result.input_tokens
            + extraction_result.input_tokens
        )
        total_output_tokens = (
            query_result.output_tokens
            + extraction_result.output_tokens
        )

        self._safe_finish_succeeded_run(
            run_id=agent_run.run_id,
            retrieved_document_count=len(documents),
            saved_evidence_count=len(saved_evidences),
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )

        return ResearcherExecutionResponse(
            subtask_id=subtask_id,
            query_rewrite_output=query_result.query_output,
            retrieved_document_count=len(documents),
            saved_evidences=saved_evidences,
            failed_queries=failed_queries,
            skipped_duplicate_source_urls=skipped_duplicate_source_urls,
        )

    def _build_validated_evidence_drafts(
        self,
        extraction_candidates,
        documents: list[RetrievedDocument],
        source_type: SourceType,
    ) -> list[EvidenceDraft]:
        """
        校验模型选择的 URL 来自本轮候选资料，
        并由服务端从真实检索结果中生成原文 Evidence。

        关键原则：
        模型只能选择来源；
        content_excerpt 必须由服务端直接从 document.content 提取。
        """
        documents_by_url = {
            self._normalize_url(str(document.url)): document
            for document in documents
        }

        evidence_drafts: list[EvidenceDraft] = []

        for candidate in extraction_candidates:
            normalized_url = self._normalize_url(
                str(candidate.source_url)
            )
            document = documents_by_url.get(normalized_url)

            if document is None:
                raise InvalidExtractedEvidenceError(
                    "Evidence Extraction Agent 引用了不属于"
                    "本轮候选资料的 URL。"
                )

            content_excerpt = self._build_server_grounded_excerpt(
                document.content
            )

            evidence_drafts.append(
                EvidenceDraft(
                    source_title=document.title,
                    source_url=document.url,
                    source_type=source_type,
                    published_at=None,
                    evidence_kind=candidate.evidence_kind,
                    content_excerpt=content_excerpt,
                    evidence_summary=candidate.evidence_summary,
                    relevance_score=candidate.relevance_score,
                    source_quality_hint=candidate.source_quality_hint,
                )
            )

        return evidence_drafts

    @staticmethod
    def _build_server_grounded_excerpt(
        document_content: str,
    ) -> str:
        """
        从检索系统返回的真实文本中直接生成证据摘录。

        该方法不调用模型、不改写事实。
        仅统一空白，并截取前 1500 个字符，
        保证写入数据库的摘录一定可追溯到候选资料。
        """
        normalized_content = re.sub(
            r"\s+",
            " ",
            document_content,
        ).strip()

        if len(normalized_content) < 20:
            raise InvalidExtractedEvidenceError(
                "候选资料缺少足够长的原始文本，"
                "无法生成可追溯的 Evidence。"
            )

        return normalized_content[:1500]

    @staticmethod
    def _normalize_url(url: str) -> str:
        """
        统一 URL 格式，用于匹配模型选择与候选资料。
        """
        url_without_fragment, _ = urldefrag(url)
        parts = urlsplit(url_without_fragment)

        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                parts.path.rstrip("/"),
                parts.query,
                "",
            )
        )

    def _safe_finish_succeeded_run(
        self,
        run_id: UUID,
        retrieved_document_count: int,
        saved_evidence_count: int,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        尽力记录成功执行指标。
        """
        try:
            self._agent_run_service.finish_run(
                run_id=run_id,
                payload=AgentRunFinish(
                    status=AgentRunStatus.SUCCEEDED,
                    output_summary=(
                        f"融合 {retrieved_document_count} 条候选资料，"
                        f"保存 {saved_evidence_count} 条新 Evidence。"
                    ),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=0.0,
                ),
            )
        except Exception:
            pass

    def _safe_finish_failed_run(
        self,
        run_id: UUID,
        error_message: str,
    ) -> None:
        """
        尽力记录失败执行信息。
        """
        try:
            self._agent_run_service.finish_run(
                run_id=run_id,
                payload=AgentRunFinish(
                    status=AgentRunStatus.FAILED,
                    error_message=error_message,
                ),
            )
        except Exception:
            pass

    def _safe_mark_task_failed(
        self,
        task_id: UUID,
        error_message: str,
    ) -> None:
        """
        Researcher 失败时将任务标记为 FAILED。
        """
        try:
            task = self._task_service.get_task(task_id)

            if task is not None and task.status == TaskStatus.RESEARCHING:
                self._task_service.transition_task_status(
                    task_id=task_id,
                    payload=TaskStatusUpdate(
                        status=TaskStatus.FAILED,
                        error_message=error_message,
                    ),
                )
        except Exception:
            pass
