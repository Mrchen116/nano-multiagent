from nano_multiagent.tools.builtins import builtin_tools


def _task_schema() -> dict[str, object]:
    tool_by_name = {tool.name: tool for tool in builtin_tools()}
    assert "task" in tool_by_name
    return dict(tool_by_name["task"].input_schema)


def test_task_tool_schema_freezes_public_surface() -> None:
    schema = _task_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["mode"]

    properties = schema["properties"]
    assert "mode" in properties
    assert "prompt" in properties
    assert "session_id" in properties
    assert "category" in properties
    assert "subagent_type" in properties
    assert "idempotency_key" in properties
    assert "timeout_seconds" in properties

    mode_schema = dict(properties["mode"])
    assert mode_schema["type"] == "string"
    assert mode_schema["enum"] == ["blocking", "non_blocking"]
