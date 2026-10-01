"""Tool discovery must not erase PA declarations or enable optional tools."""

from personal_assistant.reporter.capability_projection import (
    PA_DEFAULT_TOOL_IDS,
    PA_OPTIONAL_TOOL_IDS,
    project_tools,
)


def test_missing_runtime_tools_retain_declared_candidates_and_defaults() -> None:
    tools = project_tools((("read", "User override"), ("custom", "Custom reader")))
    declared = (*PA_DEFAULT_TOOL_IDS, *PA_OPTIONAL_TOOL_IDS)
    assert [tool["name"] for tool in tools] == [*declared, "custom"]
    assert tools[0]["description"] == "User override"
    assert {tool["name"] for tool in tools if tool["default_on"]} == set(
        PA_DEFAULT_TOOL_IDS
    )
    memory = next(tool for tool in tools if tool["name"] == "memory")
    assert memory == {"name": "memory", "description": "", "default_on": True}
    assert tools[-1] == {
        "name": "custom",
        "description": "Custom reader",
        "default_on": False,
    }
