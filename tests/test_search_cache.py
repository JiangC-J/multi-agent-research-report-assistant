import asyncio

from redis.exceptions import RedisError

from app.schemas.search import SearchResponse, SearchResult
from app.services.search_cache_service import SearchCacheService


class FakeRedis:
    """使用 Python 字典模拟 Redis 的最小行为。"""

    def __init__(self) -> None:
        self.storage: dict[str, str] = {}
        self.setex_calls: list[tuple[str, int, str]] = []

    async def get(self, key: str):
        return self.storage.get(key)

    async def setex(
        self,
        key: str,
        ttl_seconds: int,
        value: str,
    ):
        self.storage[key] = value
        self.setex_calls.append(
            (key, ttl_seconds, value)
        )


class FailingRedis:
    """模拟 Redis 不可用。"""

    async def get(self, key: str):
        raise RedisError("Redis is unavailable")

    async def setex(
        self,
        key: str,
        ttl_seconds: int,
        value: str,
    ):
        raise RedisError("Redis is unavailable")


def create_search_response() -> SearchResponse:
    """创建一条合法的统一搜索结果。"""
    return SearchResponse(
        query="enterprise ai agent risks",
        results=[
            SearchResult(
                title="AI Agent 风险研究",
                url="https://example.com/ai-agent-risks",
                content="这是一段用于缓存测试的检索结果内容。",
                relevance_score=0.9,
            )
        ],
    )


def test_search_cache_can_write_and_read_response():
    """
    写入缓存后，相同查询和相同 max_results 应能读回合法结果。
    """
    fake_redis = FakeRedis()

    cache_service = SearchCacheService(
        redis_client=fake_redis,
        ttl_seconds=3600,
    )

    search_response = create_search_response()

    asyncio.run(
        cache_service.set(
            search_response=search_response,
            max_results=5,
        )
    )

    cached_response = asyncio.run(
        cache_service.get(
            query="  ENTERPRISE   AI agent risks  ",
            max_results=5,
        )
    )

    assert cached_response is not None
    assert cached_response.query == (
        "enterprise ai agent risks"
    )
    assert cached_response.results[0].title == "AI Agent 风险研究"
    assert fake_redis.setex_calls[0][1] == 3600


def test_search_cache_uses_different_key_for_different_max_results():
    """
    相同查询但结果数量不同，不能复用同一缓存。
    """
    fake_redis = FakeRedis()

    cache_service = SearchCacheService(
        redis_client=fake_redis,
        ttl_seconds=3600,
    )

    search_response = create_search_response()

    asyncio.run(
        cache_service.set(
            search_response=search_response,
            max_results=5,
        )
    )

    cached_response = asyncio.run(
        cache_service.get(
            query="enterprise ai agent risks",
            max_results=10,
        )
    )

    assert cached_response is None


def test_search_cache_redis_failure_does_not_raise_error():
    """
    Redis 不可用时，缓存层必须安全降级，不允许阻断搜索主流程。
    """
    cache_service = SearchCacheService(
        redis_client=FailingRedis(),
        ttl_seconds=3600,
    )

    cached_response = asyncio.run(
        cache_service.get(
            query="enterprise ai agent risks",
            max_results=5,
        )
    )

    asyncio.run(
        cache_service.set(
            search_response=create_search_response(),
            max_results=5,
        )
    )

    assert cached_response is None