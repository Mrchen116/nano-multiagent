from dataclasses import fields

from agent.core.types import Message, ToolCall, ToolResult, ToolSpec, TurnResult


def test_message_contract_fields_are_stable() -> None:
    assert [field.name for field in fields(Message)] == [
        "message_id",
        "role",
        "content",
        "name",
        "tool_call_id",
        "parent_message_id",
        "group_id",
        "metadata",
        "reasoning_content",
        "reasoning_signature",
    ]


def test_tool_contract_fields_are_stable() -> None:
    assert [field.name for field in fields(ToolSpec)] == [
        "name",
        "description",
        "input_schema",
        "is_concurrency_safe",
        "max_result_size_chars",
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
        "content",
        "duration_ms",
        "arguments",
        # bugfix-410-M2 (#82/#97): sidecar badge classification, separate from error.
        "reason_code",
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
