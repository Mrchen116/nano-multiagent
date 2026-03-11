from dataclasses import fields

from agent.core.types import Message, ToolCall, ToolResult, ToolSpec, TurnResult


def test_message_contract_fields_are_stable() -> None:
    assert [field.name for field in fields(Message)] == [
        "message_id",
        "role",
        "content",
        "name",
        "tool_call_id",
        "metadata",
    ]


def test_tool_contract_fields_are_stable() -> None:
    assert [field.name for field in fields(ToolSpec)] == [
        "name",
        "description",
        "input_schema",
    ]
    assert [field.name for field in fields(ToolCall)] == [
        "call_id",
        "name",
        "arguments",
    ]
    assert [field.name for field in fields(ToolResult)] == [
        "call_id",
        "name",
        "output",
        "error",
    ]


def test_turn_result_contract_fields_are_stable() -> None:
    assert [field.name for field in fields(TurnResult)] == [
        "session_id",
        "turn_id",
        "messages",
        "tool_calls",
        "tool_results",
        "completed",
        "stop_reason",
        "usage",
    ]
