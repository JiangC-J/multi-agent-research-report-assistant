import hashlib
import json
import logging

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.schemas.search import SearchResponse


logger = logging.getLogger(__name__)


class SearchCacheService:
    """
    Tavily 搜索结果的 Redis 缓存服务。

    缓存失败时采用 fail-open 策略：
    即 Redis 出错只会导致缓存未命中，
    不会阻断真实的 Tavily 搜索请求。
    """

    CACHE_KEY_PREFIX = "research-agent:search-cache:v1"

    def __init__(
        self,
        redis_client: Redis,
        ttl_seconds: int,
    ) -> None:
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

    async def get(
        self,
        query: str,
        max_results: int,
    ) -> SearchResponse | None:
        """
        读取缓存。

        返回 None 代表缓存未命中、缓存内容无效，
        或 Redis 暂时不可用。
        """
        cache_key = self._build_cache_key(
            query=query,
            max_results=max_results,
        )

        try:
            cached_value = await self._redis_client.get(cache_key)
        except RedisError as error:
            logger.warning(
                "Redis 读取搜索缓存失败，将降级为真实检索：%s",
                error,
            )
            return None

        if cached_value is None:
            return None

        try:
            return SearchResponse.model_validate_json(cached_value)
        except (ValidationError, ValueError) as error:
            logger.warning(
                "Redis 搜索缓存格式无效，将降级为真实检索：%s",
                error,
            )
            return None

    async def set(
        self,
        search_response: SearchResponse,
        max_results: int,
    ) -> None:
        """
        写入缓存。

        写入失败只记录日志，不影响调用方拿到真实搜索结果。
        """
        cache_key = self._build_cache_key(
            query=search_response.query,
            max_results=max_results,
        )

        cache_value = json.dumps(
            search_response.model_dump(mode="json"),
            ensure_ascii=False,
        )

        try:
            await self._redis_client.setex(
                cache_key,
                self._ttl_seconds,
                cache_value,
            )
        except RedisError as error:
            logger.warning(
                "Redis 写入搜索缓存失败，将继续返回真实检索结果：%s",
                error,
            )

    @classmethod
    def _build_cache_key(
        cls,
        query: str,
        max_results: int,
    ) -> str:
        """
        为一次搜索构造稳定、不泄露原始查询内容的 Redis Key。

        同一查询忽略首尾空格和大小写后会共享缓存；
        max_results 不同则视为不同缓存结果。
        """
        normalized_query = " ".join(
            query.casefold().split()
        )

        key_payload = (
            f"{normalized_query}|max_results={max_results}"
        )

        query_hash = hashlib.sha256(
            key_payload.encode("utf-8")
        ).hexdigest()

        return f"{cls.CACHE_KEY_PREFIX}:{query_hash}"