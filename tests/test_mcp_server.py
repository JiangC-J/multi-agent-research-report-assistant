from app.mcp_server import (
    build_report_review_prompt,
    read_execution_trace,
    read_final_report,
    read_research_task,
)


INVALID_TASK_ID = "not-a-valid-uuid"
MISSING_TASK_ID = "00000000-0000-0000-0000-000000000000"


def test_read_research_task_rejects_invalid_uuid() -> None:
    result = read_research_task(INVALID_TASK_ID)

    assert result["ok"] is False
    assert result["error"] == "task_id 格式不正确，必须是合法的 UUID。"


def test_read_final_report_rejects_invalid_uuid() -> None:
    result = read_final_report(INVALID_TASK_ID)

    assert result["ok"] is False
    assert result["error"] == "task_id 格式不正确，必须是合法的 UUID。"


def test_read_execution_trace_rejects_invalid_uuid() -> None:
    result = read_execution_trace(INVALID_TASK_ID)

    assert result["ok"] is False
    assert result["error"] == "task_id 格式不正确，必须是合法的 UUID。"


def test_read_research_task_returns_structured_not_found() -> None:
    result = read_research_task(MISSING_TASK_ID)

    assert result["ok"] is False
    assert result["task_id"] == MISSING_TASK_ID
    assert result["error"] == "未找到对应的研究任务。"


def test_build_report_review_prompt_contains_required_rules() -> None:
    prompt = build_report_review_prompt(
        task_id=MISSING_TASK_ID,
        audience="企业管理者",
    )

    assert "get_research_task" in prompt
    assert "get_final_report" in prompt
    assert "get_execution_trace" in prompt
    assert "不得编造" in prompt
    assert "企业管理者" in prompt