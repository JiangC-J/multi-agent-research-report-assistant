from functools import lru_cache

import httpx
from langchain_openai import ChatOpenAI

from app.core.config import get_settings


@lru_cache(maxsize=4)
def get_sync_http_client(
    timeout_seconds: int,
) -> httpx.Client:
    """
    创建同步 HTTP 客户端。

    trust_env=False 表示不继承系统中的代理环境配置，
    避免模型请求被 VPN、代理工具或终端环境变量错误转发。
    """
    return httpx.Client(
        timeout=httpx.Timeout(timeout_seconds),
        trust_env=False,
    )


@lru_cache(maxsize=4)
def get_async_http_client(
    timeout_seconds: int,
) -> httpx.AsyncClient:
    """
    创建异步 HTTP 客户端。

    Agent 使用 ainvoke，因此实际模型请求主要走该客户端。
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        trust_env=False,
    )


def create_chat_model() -> ChatOpenAI:
    """
    根据环境变量创建 OpenAI 兼容的大模型客户端。
    """
    settings = get_settings()

    model_kwargs: dict[str, object] = {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key.get_secret_value(),
        "temperature": settings.llm_temperature,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
        "max_tokens": settings.llm_max_tokens,
        "http_client": get_sync_http_client(
            settings.llm_timeout_seconds
        ),
        "http_async_client": get_async_http_client(
            settings.llm_timeout_seconds
        ),
        # 已显式提供 HTTP 客户端，因此不需要 LangChain 再注入
        # 自定义 socket transport。这样可以避免系统代理检测干扰。
        "http_socket_options": (),
    }

    if settings.llm_base_url:
        model_kwargs["base_url"] = settings.llm_base_url

    is_deepseek_v4_flash = (
        settings.llm_model
        == "deepseek-ai/DeepSeek-V4-Flash"
    )

    if (
        is_deepseek_v4_flash
        and settings.llm_thinking_budget is not None
    ):
        model_kwargs["extra_body"] = {
            "thinking_budget": settings.llm_thinking_budget,
        }

    return ChatOpenAI(**model_kwargs)
