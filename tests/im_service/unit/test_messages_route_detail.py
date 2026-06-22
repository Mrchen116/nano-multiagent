"""feat-409 Round1 fix 1/2: REST message serialization carries detail + real input.

The HTTP history path (GET /conversations/{id}/messages) has its own Pydantic
serializer ``to_message_response`` / ``ToolCallPayload`` independent of the WS
streaming path. Before the fix it dropped ``detail`` (front-end history load
退化 <pre>{output}>) and only had id/name/status/input/duration_ms/output.
"""

from __future__ import annotations

from IM.api.routes.messages import to_message_response
from IM.domain.models import Actor, Message, ToolCall


def _message_with_tool_call(tc: ToolCall) -> Message:
    return Message(
        id="m1",
        conversation_id="c1",
        sender=Actor(type="agent", id="a1", display_name="Agent"),
        sender_user_id="a1",
        sender_type="agent",
        content="hi",
        created_at="2026-01-01T00:00:00Z",
        tool_calls=[tc],
    )


def test_to_message_response_carries_detail() -> None:
    detail = {
        "command": "pytest -q",
        "exit_code": 0,
        "stdout": "OK",
        "stderr": "",
        "truncated": False,
    }
    tc = ToolCall(
        id="tc1",
        name="bash",
        status="completed",
        duration_ms=12,
        input={"command": "pytest -q", "description": "跑测试"},
        output="跑测试",
        detail=detail,
    )
    resp = to_message_response(_message_with_tool_call(tc))
    assert resp.tool_calls[0].detail == detail


def test_to_message_response_preserves_input() -> None:
    # fix 2: REST must return the real args, not {} (input must survive).
    tc = ToolCall(
        id="tc1",
        name="bash",
        status="completed",
        duration_ms=12,
        input={"command": "pytest -q", "description": "跑测试"},
        output="跑测试",
    )
    resp = to_message_response(_message_with_tool_call(tc))
    assert resp.tool_calls[0].input == {
        "command": "pytest -q",
        "description": "跑测试",
    }


def test_to_message_response_detail_absent_is_none() -> None:
    tc = ToolCall(id="tc1", name="read", status="completed", output="42 lines")
    resp = to_message_response(_message_with_tool_call(tc))
    assert resp.tool_calls[0].detail is None


def test_to_message_response_carries_emoji() -> None:
    # feat-425 决策 2: REST 历史路径必须序列化 emoji,否则重载后自定义工具图标丢失。
    tc = ToolCall(
        id="tc1",
        name="web_fetch",
        status="completed",
        input={"url": "https://x"},
        output="https://x",
        emoji="🌐",
    )
    resp = to_message_response(_message_with_tool_call(tc))
    assert resp.tool_calls[0].emoji == "🌐"


def test_to_message_response_emoji_absent_is_none() -> None:
    tc = ToolCall(id="tc1", name="read", status="completed", output="42 lines")
    resp = to_message_response(_message_with_tool_call(tc))
    assert resp.tool_calls[0].emoji is None
