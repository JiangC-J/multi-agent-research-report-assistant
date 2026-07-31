from app import mcp_server


INVALID_TASK_ID = "not-a-valid-uuid"
MISSING_TASK_ID = "00000000-0000-0000-0000-000000000000"


class MissingTaskService:
    """
    测试专用的假服务。

    不连接真实数据库，固定模拟“任务不存在”的业务结果。
    """

    def get_task(self, task_id: object) -> None:
        return None


def test_read_research_task_rejects_invalid_uuid() -> None:
    result = mcp_server.read_research_task(INVALID_TASK_ID)

    assert result["ok"] is False
    assert result["error"] == "task_id 格式不正确，必须是合法的 UUID。"


def test_read_final_report_rejects_invalid_uuid() -> None:
    result = mcp_server.read_final_report(INVALID_TASK_ID)

    assert result["ok"] is False
    assert result["error"] == "task_id 格式不正确，必须是合法的 UUID。"


def test_read_execution_trace_rejects_invalid_uuid() -> None:
    result = mcp_server.read_execution_trace(INVALID_TASK_ID)

    assert result["ok"] is False
    assert result["error"] == "task_id 格式不正确，必须是合法的 UUID。"


def test_read_research_task_returns_structured_not_found(
    monkeypatch: object,
) -> None:
    """
    用 Fake Service 隔离数据库，只测试 MCP 层的返回契约。
    """
    monkeypatch.setattr(
        mcp_server,
        "get_research_task_service",
        lambda: MissingTaskService(),
    )

    result = mcp_server.read_research_task(MISSING_TASK_ID)

    assert result["ok"] is False
    assert result["task_id"] == MISSING_TASK_ID
    assert result["error"] == "未找到对应的研究任务。"


def test_build_report_review_prompt_contains_required_rules() -> None:
    prompt = mcp_server.build_report_review_prompt(
        task_id=MISSING_TASK_ID,
        audience="企业管理者",
    )

    assert "get_research_task" in prompt
    assert "get_final_report" in prompt
    assert "get_execution_trace" in prompt
    assert "不得编造" in prompt
    assert "企业管理者" in prompt