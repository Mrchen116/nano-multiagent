from agent.platform.tools.builtins import builtin_tools


def _task_schema() -> dict[str, object]:
    tool_by_name = {tool.name: tool for tool in builtin_tools()}
    assert "task" in tool_by_name
    return dict(tool_by_name["task"].input_schema)


def test_task_tool_schema_freezes_public_surface() -> None:
    schema = _task_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["load_skills", "description", "prompt", "run_in_background"]

    properties = schema["properties"]
    assert "load_skills" in properties
    assert "description" in properties
    assert "prompt" in properties
    assert "run_in_background" in properties
    assert "session_id" in properties
    assert "category" in properties
    assert "subagent_type" in properties
    assert "command" in properties
    assert "idempotency_key" in properties
    assert "timeout_seconds" in properties
    assert "mode" not in properties

    load_skills_schema = dict(properties["load_skills"])
    assert load_skills_schema["type"] == "array"
    assert load_skills_schema["items"]["type"] == "string"

    run_in_background_schema = dict(properties["run_in_background"])
    assert run_in_background_schema["type"] == "boolean"
