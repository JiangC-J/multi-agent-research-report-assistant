from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用运行配置。

    默认从项目根目录的 .env 文件读取。
    配置集中在这里，业务代码不直接读取环境变量。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_api_key: SecretStr
    llm_model: str
    llm_base_url: str | None = None
    llm_temperature: float = 0.2
    llm_timeout_seconds: int = 180
    llm_max_retries: int = 0
    llm_max_tokens: int = 2048
    llm_thinking_budget: int | None = 512

    tavily_api_key: SecretStr | None = None
    tavily_max_results: int = 5

    # Redis 的连接地址。
    # /0 表示使用 Redis 的第 0 个逻辑数据库。
    redis_url: str = "redis://localhost:6379/0"

    # 建立连接最多等待多久，避免 Redis 不可用时请求长期卡住。
    redis_socket_connect_timeout_seconds: float = 5.0

    # 单次 Redis 读写操作最多等待多久。
    redis_socket_timeout_seconds: float = 5.0

        # Tavily 搜索结果在 Redis 中的缓存时长，单位：秒。
    search_cache_ttl_seconds: int = 3600

        # Celery 的消息队列地址。
    # 使用 Redis 第 1 个逻辑数据库，避免和搜索缓存混在一起。
    celery_broker_url: str = "redis://localhost:6379/1"

    # Celery 执行结果的保存地址。
    # 使用 Redis 第 2 个逻辑数据库。
    celery_result_backend: str = "redis://localhost:6379/2"

    # 单个后台任务的硬超时时间，超时后 Celery 会终止任务。
    celery_task_time_limit_seconds: int = 600

    # 软超时比硬超时更早触发，让任务有机会记录失败原因。
    celery_task_soft_time_limit_seconds: int = 540


@lru_cache
def get_settings() -> Settings:
    """
    获取并缓存应用配置。

    同一个进程内只创建一次 Settings，
    避免每个请求都重新读取 .env。
    """
    return Settings()