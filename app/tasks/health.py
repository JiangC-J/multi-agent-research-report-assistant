from app.core.celery_app import celery_app


@celery_app.task(
    name="research_agent.health_check",
)
def celery_health_check() -> dict[str, str]:
    """
    最小后台任务。

    用于确认：
    任务能否被投递到 Redis、
    Worker 能否消费、
    执行结果能否写回 Result Backend。
    """
    return {
        "status": "ok",
        "worker": "ready",
    }