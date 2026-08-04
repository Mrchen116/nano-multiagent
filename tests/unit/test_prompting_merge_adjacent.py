"""Assistant-history merge behavior through the model-consumer entry point."""

from __future__ import annotations

from agent.core.agent.prompting import build_chat_messages
from agent.core.types import Message


def _tool_call(call_id: str) -> dict[str, object]:
    return {"call_id": call_id, "name": "read", "arguments": {"path": call_id}}


def _assistant(
    message_id: str,
    content: str,
    *,
    group_id: str | None = None,
    tool_calls: list[dict[str, object]] | None = None,
    reasoning_content: str | None = None,
    reasoning_signature: str | None = None,
) -> Message:
    metadata = {"tool_calls": tool_calls} if tool_calls else {}
    return Message(
        message_id=message_id,
        role="assistant",
        content=content,
        group_id=group_id,
        metadata=metadata,
        reasoning_content=reasoning_content,
        reasoning_signature=reasoning_signature,
    )


def test_adjacent_assistant_history_reaches_the_model_as_one_complete_turn() -> None:
    messages = build_chat_messages(
        history_messages=(
            _assistant(
                "a1",
                "TEXT_ONE",
                tool_calls=[_tool_call("call-1")],
                reasoning_content="REASONING_INPUT_SENTINEL",
                reasoning_signature="SIGNATURE_INPUT_SENTINEL",
            ),
            _assistant(
                "a2",
                "TEXT_TWO",
                tool_calls=[_tool_call("call-2")],
            ),
        ),
        user_text="USER_INPUT_SENTINEL",
    )

    assert [message.role for message in messages] == ["assistant", "user"]
    assistant = messages[0]
    assert assistant.content == "TEXT_ONETEXT_TWO"
    assert [call.call_id for call in assistant.tool_calls] == ["call-1", "call-2"]
    assert assistant.reasoning_content == "REASONING_INPUT_SENTINEL"
    assert assistant.reasoning_signature == "SIGNATURE_INPUT_SENTINEL"


def test_nonadjacent_assistant_history_remains_separate_for_the_model() -> None:
    messages = build_chat_messages(
        history_messages=(
            _assistant("a1", "TEXT_ONE"),
            Message(
                message_id="tool-1",
                role="tool",
                content="TOOL_RESULT_SENTINEL",
                tool_call_id="call-1",
            ),
            _assistant("a2", "TEXT_TWO"),
        ),
        user_text="USER_INPUT_SENTINEL",
    )

    assert [message.role for message in messages] == [
        "assistant",
        "tool",
        "assistant",
        "user",
    ]
    assert messages[0].content == "TEXT_ONE"
    assert messages[1].content == "TOOL_RESULT_SENTINEL"
    assert messages[2].content == "TEXT_TWO"


def test_persisted_rows_in_one_assistant_group_restore_before_tool_results() -> None:
    messages = build_chat_messages(
        history_messages=(
            _assistant(
                "a1",
                "TEXT_ONE",
                group_id="group-1",
                tool_calls=[_tool_call("call-1")],
                reasoning_content="REASONING_INPUT_SENTINEL",
                reasoning_signature="SIGNATURE_INPUT_SENTINEL",
            ),
            Message(
                message_id="tool-1",
                role="tool",
                content="TOOL_RESULT_SENTINEL",
                tool_call_id="call-1",
            ),
            _assistant(
                "a2",
                "TEXT_TWO",
                group_id="group-1",
                tool_calls=[_tool_call("call-2")],
            ),
        ),
        user_text="USER_INPUT_SENTINEL",
    )

    assert [message.role for message in messages] == ["assistant", "tool", "user"]
    assistant = messages[0]
    assert assistant.content == "TEXT_ONETEXT_TWO"
    assert [call.call_id for call in assistant.tool_calls] == ["call-1", "call-2"]
    assert assistant.reasoning_content == "REASONING_INPUT_SENTINEL"
    assert assistant.reasoning_signature == "SIGNATURE_INPUT_SENTINEL"
