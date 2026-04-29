from agent.platform.tools.builtins import builtin_tools


def _agent_schema() -> dict[str, object]:
    tool_by_name = {tool.name: tool for tool in builtin_tools()}
    assert "agent" in tool_by_name
    return dict(tool_by_name["agent"].input_schema)


def test_agent_tool_schema_freezes_public_surface() -> None:
    schema = _agent_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["load_skills", "description", "prompt"]

    properties = schema["properties"]
    assert "load_skills" in properties
    assert "description" in properties
    assert "prompt" in properties
    assert "run_in_background" in properties
    assert "agent_id" in properties
    assert "category" in properties
    assert "subagent_type" in properties
    assert "timeout_seconds" in properties
    assert "session_id" not in properties
    assert "command" not in properties
    assert "mode" not in properties

    load_skills_schema = dict(properties["load_skills"])
    assert load_skills_schema["type"] == "array"
    assert load_skills_schema["items"]["type"] == "string"

    run_in_background_schema = dict(properties["run_in_background"])
    assert run_in_background_schema["type"] == "boolean"
