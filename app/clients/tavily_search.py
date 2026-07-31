from tavily import AsyncTavilyClient

from app.core.config import get_settings
from app.schemas.search import SearchResponse, SearchResult
from app.services.search_cache_service import SearchCacheService


class TavilyConfigurationError(Exception):
    """
    未配置 Tavily API Key 时抛出。
    """


class TavilySearchClient:
    """
    Tavily 异步网页搜索客户端。

    当注入 SearchCacheService 后，
    会优先从 Redis 读取搜索结果缓存。
    """

    def __init__(
        self,
        search_cache_service: SearchCacheService | None = None,
    ) -> None:
        settings = get_settings()

        if settings.tavily_api_key is None:
            raise TavilyConfigurationError(
                "未配置 TAVILY_API_KEY，请检查 .env 文件。"
            )

        self._default_max_results = settings.tavily_max_results
        self._search_cache_service = search_cache_service

        self._client = AsyncTavilyClient(
            api_key=settings.tavily_api_key.get_secret_value(),
        )

    async def search(
        self,
        query: str,
        max_results: int | None = None,
    ) -> SearchResponse:
        """
        查询 Tavily。

        先查 Redis 缓存；未命中才访问 Tavily；
        成功返回真实结果后再尝试写入缓存。
        """
        effective_max_results = (
            max_results or self._default_max_results
        )

        if self._search_cache_service is not None:
            cached_response = await self._search_cache_service.get(
                query=query,
                max_results=effective_max_results,
            )

            if cached_response is not None:
                return cached_response

        response = await self._client.search(
            query=query,
            search_depth="basic",
            max_results=effective_max_results,
            include_raw_content=False,
        )

        normalized_results = [
            SearchResult(
                title=item.get("title") or item["url"],
                url=item["url"],
                content=item.get("content")
                or item.get("raw_content")
                or "",
                relevance_score=float(item.get("score") or 0.0),
            )
            for item in response.get("results", [])
            if item.get("url")
        ]

        search_response = SearchResponse(
            query=query,
            results=normalized_results,
        )

        if self._search_cache_service is not None:
            await self._search_cache_service.set(
                search_response=search_response,
                max_results=effective_max_results,
            )

        return search_response