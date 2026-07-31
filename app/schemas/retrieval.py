from pydantic import BaseModel, Field, HttpUrl

from app.schemas.research_query import QueryRewriteOutput


class FailedSearchQuery(BaseModel):
    """
    单条查询执行失败时的记录。
    """

    query: str = Field(
        ...,
        description="执行失败的检索查询。",
    )
    error_message: str = Field(
        ...,
        description="失败原因。",
    )


class RetrievedDocument(BaseModel):
    """
    多查询融合后的候选资料。
    """

    title: str = Field(
        ...,
        description="来源标题。",
    )
    url: HttpUrl = Field(
        ...,
        description="来源链接。",
    )
    content: str = Field(
        ...,
        description="搜索服务返回的内容片段。",
    )
    provider_score: float = Field(
        ...,
        ge=0.0,
        description="搜索服务提供的原始相关性分数。",
    )
    rrf_score: float = Field(
        ...,
        ge=0.0,
        description="多个查询融合后的 RRF 分数。",
    )
    source_queries: list[str] = Field(
        ...,
        min_length=1,
        description="找到该资料的改写查询列表。",
    )


class MultiQueryRetrievalResponse(BaseModel):
    """
    Query Rewrite 与多查询检索的完整输出。
    """

    query_rewrite_output: QueryRewriteOutput = Field(
        ...,
        description="本次实际执行的改写查询。",
    )
    documents: list[RetrievedDocument] = Field(
        default_factory=list,
        description="去重、融合后的候选资料。",
    )
    failed_queries: list[FailedSearchQuery] = Field(
        default_factory=list,
        description="个别失败的查询记录。",
    )