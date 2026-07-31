from celery import Celery

from app.core.config import get_settings


settings = get_settings()


celery_app = Celery(
    "multi_agent_research_assistant",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
        include=[
        "app.tasks.health",
        "app.tasks.research_workflow",
    ],
)


celery_app.conf.update(
    # 使用 JSON，避免不安全的 Python 对象序列化。
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # 任务进入运行状态时，结果后端可查询到 STARTED。
    task_track_started=True,

    # Worker 启动时 Redis 暂时不可用，则继续重试连接。
    broker_connection_retry_on_startup=True,

    # 任务超时保护。
    task_time_limit=settings.celery_task_time_limit_seconds,
    task_soft_time_limit=(
        settings.celery_task_soft_time_limit_seconds
    ),

    # 每次只预取一个任务。
    # 长任务场景下，避免某个 Worker 提前拿走很多任务，
    # 导致其他 Worker 空闲而任务仍在排队。
    worker_prefetch_multiplier=1,

    timezone="Asia/Shanghai",
    enable_utc=False,
)