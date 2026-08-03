"""REST history serialization regressions for message process details."""

from IM.api.routes.messages import to_message_response
from IM.domain.models import Actor, Message, ThinkingSegment, ToolCall


def _agent_message(
    *,
    tool_calls: list[ToolCall] | None = None,
    thinking: list[ThinkingSegment] | None = None,
) -> Message:
    return Message(
        id="m1",
        conversation_id="c1",
        sender=Actor(type="agent", id="a1", display_name="Agent"),
        sender_user_id="a1",
        sender_type="agent",
        content="answer",
        created_at="2026-01-01T00:00:00Z",
        thinking=thinking,
        tool_calls=tool_calls,
    )


def test_message_response_preserves_process_details_for_history() -> None:
    detail = {
        "command": "pytest -q",
        "exit_code": 0,
        "stdout": "OK",
        "stderr": "",
        "truncated": False,
    }
    response = to_message_response(
        _agent_message(
            thinking=[ThinkingSegment(seq=0, text="inspect state")],
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="bash",
                    status="completed",
                    input={"command": "pytest -q", "description": "run tests"},
                    output="tests passed",
                    detail=detail,
                    emoji="🧪",
                )
            ],
        )
    )

    assert [(segment.seq, segment.text) for segment in response.thinking] == [
        (0, "inspect state")
    ]
    assert response.tool_calls[0].input == {
        "command": "pytest -q",
        "description": "run tests",
    }
    assert response.tool_calls[0].detail == detail
    assert response.tool_calls[0].emoji == "🧪"


def test_message_response_uses_legacy_process_defaults() -> None:
    response = to_message_response(
        _agent_message(tool_calls=[ToolCall(id="tc1", name="read", status="completed")])
    )

    assert response.thinking == []
    assert response.tool_calls[0].detail is None
    assert response.tool_calls[0].emoji is None
