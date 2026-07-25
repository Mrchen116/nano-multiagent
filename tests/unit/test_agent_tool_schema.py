from agent.platform.tools.builtins import builtin_tools


def _agent_schema() -> dict[str, object]:
    tool_by_name = {tool.name: tool for tool in builtin_tools()}
    assert "agent" in tool_by_name
    return dict(tool_by_name["agent"].input_schema)


def test_agent_tool_schema_freezes_public_surface() -> None:
    """feat-474: schema drops the load_skills/category/timeout_seconds ritual
    fields — `additionalProperties: False` (already generically enforced by
    `_validate_args`, see `test_tool_validation_errors.py`) makes any caller
    still passing them fail loudly instead of being silently ignored.
    """
    schema = _agent_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["description", "prompt"]

    properties = schema["properties"]
    assert "description" in properties
    assert "prompt" in properties
    assert "run_in_background" in properties
    assert "agent_id" in properties
    assert "subagent_type" in properties
    assert "session_id" not in properties
    assert "command" not in properties
    assert "mode" not in properties
    assert "load_skills" not in properties
    assert "category" not in properties
    assert "timeout_seconds" not in properties

    subagent_type_schema = dict(properties["subagent_type"])
    assert subagent_type_schema["type"] == "string"

    run_in_background_schema = dict(properties["run_in_background"])
    assert run_in_background_schema["type"] == "boolean"


def test_agent_tool_description_lists_built_in_types_and_default() -> None:
    """spec「主 agent 能知道有哪些类型可选」— the description is the model-facing
    surface for this (CC-style: not a schema enum, per design 决策 5)."""
    tool_by_name = {tool.name: tool for tool in builtin_tools()}
    description = tool_by_name["agent"].description

    assert "general-purpose" in description
    assert "Explore" in description
    assert "Plan" in description
    assert "defaults to 'general-purpose'" in description
