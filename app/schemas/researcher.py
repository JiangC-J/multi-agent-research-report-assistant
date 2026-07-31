from pydantic import BaseModel, Field, HttpUrl

from app.schemas.evidence import EvidenceResponse
from app.schemas.research_query import QueryRewriteOutput
from app.schemas.retrieval import FailedSearchQuery


class ResearcherExecutionResponse(BaseModel):
    """
    单个子任务完成检索和 Evidence 提取后的结果。
    """

    subtask_id: str = Field(
        ...,
        description="本次执行的研究子任务 ID。",
    )
    query_rewrite_output: QueryRewriteOutput = Field(
        ...,
        description="实际执行的改写查询。",
    )
    retrieved_document_count: int = Field(
        ...,
        ge=0,
        description="RRF 融合后的候选资料数量。",
    )
    saved_evidences: list[EvidenceResponse] = Field(
        default_factory=list,
        description="本次成功保存的 Evidence。",
    )
    failed_queries: list[FailedSearchQuery] = Field(
        default_factory=list,
        description="个别检索查询的失败记录。",
    )
    skipped_duplicate_source_urls: list[HttpUrl] = Field(
        default_factory=list,
        description="因同一子任务已存在而跳过的重复来源。",
    )