import asyncio
from urllib.parse import urldefrag, urlsplit, urlunsplit

from app.clients.tavily_search import TavilySearchClient
from app.schemas.research_query import RewrittenQuery
from app.schemas.retrieval import (
    FailedSearchQuery,
    RetrievedDocument,
)
from app.schemas.search import SearchResponse


class MultiQueryRetriever:
    """
    执行多查询网页检索，并进行 URL 去重与 RRF 融合。
    """

    def __init__(
        self,
        search_client: TavilySearchClient,
        rrf_k: int = 60,
    ) -> None:
        self._search_client = search_client
        self._rrf_k = rrf_k

    async def retrieve(
        self,
        queries: list[RewrittenQuery],
    ) -> tuple[list[RetrievedDocument], list[FailedSearchQuery]]:
        """
        并发执行多条查询，返回融合后的资料和失败记录。
        """
        search_tasks = [
            self._search_client.search(query=item.query)
            for item in queries
        ]

        search_outcomes = await asyncio.gather(
            *search_tasks,
            return_exceptions=True,
        )

        fused_documents: dict[str, dict] = {}
        failed_queries: list[FailedSearchQuery] = []

        for rewritten_query, outcome in zip(
            queries,
            search_outcomes,
            strict=True,
        ):
            if isinstance(outcome, Exception):
                failed_queries.append(
                    FailedSearchQuery(
                        query=rewritten_query.query,
                        error_message=str(outcome)[:1000],
                    )
                )
                continue

            self._merge_search_response(
                search_response=outcome,
                fused_documents=fused_documents,
            )

        documents = [
            RetrievedDocument(
                title=document["title"],
                url=document["url"],
                content=document["content"],
                provider_score=document["provider_score"],
                rrf_score=document["rrf_score"],
                source_queries=document["source_queries"],
            )
            for document in fused_documents.values()
        ]

        documents.sort(
            key=lambda document: document.rrf_score,
            reverse=True,
        )

        return documents, failed_queries

    def _merge_search_response(
        self,
        search_response: SearchResponse,
        fused_documents: dict[str, dict],
    ) -> None:
        """
        将一次搜索结果合并到 RRF 融合结果中。
        """
        for rank, result in enumerate(
            search_response.results,
            start=1,
        ):
            normalized_url = self._normalize_url(str(result.url))
            rrf_increment = 1 / (self._rrf_k + rank)

            existing_document = fused_documents.get(normalized_url)

            if existing_document is None:
                fused_documents[normalized_url] = {
                    "title": result.title,
                    "url": result.url,
                    "content": result.content,
                    "provider_score": result.relevance_score,
                    "rrf_score": rrf_increment,
                    "source_queries": [search_response.query],
                }
                continue

            existing_document["rrf_score"] += rrf_increment

            if result.relevance_score > existing_document["provider_score"]:
                existing_document["title"] = result.title
                existing_document["content"] = result.content
                existing_document["provider_score"] = (
                    result.relevance_score
                )

            if search_response.query not in existing_document[
                "source_queries"
            ]:
                existing_document["source_queries"].append(
                    search_response.query
                )

    @staticmethod
    def _normalize_url(url: str) -> str:
        """
        删除 URL 片段，并统一移除末尾斜杠用于去重。
        """
        url_without_fragment, _ = urldefrag(url)
        parts = urlsplit(url_without_fragment)

        normalized_path = parts.path.rstrip("/")

        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                normalized_path,
                parts.query,
                "",
            )
        )