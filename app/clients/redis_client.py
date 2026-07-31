from functools import lru_cache

import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    """
    创建并复用异步 Redis 客户端。

    Redis 客户端本身维护连接池。
    使用缓存后，同一 FastAPI 进程只会创建一套连接池，
    而不是每个请求都新建 TCP 连接。
    """
    settings = get_settings()

    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=(
            settings.redis_socket_connect_timeout_seconds
        ),
        socket_timeout=settings.redis_socket_timeout_seconds,
    )


async def close_redis_client() -> None:
    """
    在 FastAPI 服务停止时关闭 Redis 连接池。

    只有客户端实际被创建过，才需要释放。
    """
    if get_redis_client.cache_info().currsize == 0:
        return

    client = get_redis_client()
    await client.aclose()
    get_redis_client.cache_clear()