from pydantic import BaseModel, Field, HttpUrl, field_validator


class SearchRequest(BaseModel):
    """
    一次网页搜索请求。
    """

    query: str = Field(
        ...,
        min_length=3,
        max_length=300,
        description="需要执行的检索查询。",
    )
    max_results: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="本次搜索最多返回的结果数量。",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """
        清理查询首尾空白。
        """
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("query 不能只包含空白字符。")

        return cleaned_value


class SearchResult(BaseModel):
    """
    标准化后的单条搜索结果。
    """

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
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
    relevance_score: float = Field(
        ...,
        ge=0.0,
        description="搜索服务提供的相关性分数。",
    )


class SearchResponse(BaseModel):
    """
    一次搜索的标准化响应。
    """

    query: str = Field(
        ...,
        description="实际执行的查询。",
    )
    results: list[SearchResult] = Field(
        default_factory=list,
        description="标准化后的搜索结果列表。",
    )