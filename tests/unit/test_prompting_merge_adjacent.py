"""RC2 regression: _merge_adjacent_assistant must preserve reasoning fields (bugfix-376)."""

from agent.core.agent.prompting import _merge_adjacent_assistant
from agent.core.llm.interfaces import LLMMessage, LLMToolCall


def _assistant(
    content: str = "",
    *,
    tool_calls: tuple[LLMToolCall, ...] = (),
    reasoning_content: str | None = None,
    reasoning_signature: str | None = None,
) -> LLMMessage:
    return LLMMessage(
        role="assistant",
        content=content,
        tool_calls=tool_calls,
        reasoning_content=reasoning_content,
        reasoning_signature=reasoning_signature,
    )


def _tool_call(call_id: str, name: str = "read") -> LLMToolCall:
    return LLMToolCall(call_id=call_id, name=name, arguments={})


def test_merge_adjacent_assistant_preserves_reasoning_content() -> None:
    """When two adjacent assistant messages are merged, reasoning_content must not be lost.

    Bug (bugfix-376 RC2): _merge_adjacent_assistant reconstructs LLMMessage without
    reasoning_content/reasoning_signature, so any thinking block carried by the first
    message is silently dropped.  The Anthropic provider then sends an assistant turn
    with a tool_use block but no thinking block, which some providers reject.
    """
    msg1 = _assistant(
        "",
        tool_calls=(_tool_call("tc1"),),
        reasoning_content="some reasoning",
        reasoning_signature="sig-abc",
    )
    msg2 = _assistant("follow-up text")

    merged = _merge_adjacent_assistant([msg1, msg2])

    assert len(merged) == 1
    assert merged[0].reasoning_content == "some reasoning", (
        f"reasoning_content was dropped; got {merged[0].reasoning_content!r}"
    )
    assert merged[0].reasoning_signature == "sig-abc", (
        f"reasoning_signature was dropped; got {merged[0].reasoning_signature!r}"
    )


def test_merge_adjacent_assistant_preserves_reasoning_from_first_message() -> None:
    """reasoning_content from the first of several adjacent messages must survive merge."""
    msg1 = _assistant(
        "think",
        reasoning_content="deep thought",
        reasoning_signature="sig-xyz",
    )
    msg2 = _assistant(
        "conclusion",
        tool_calls=(_tool_call("tc2"),),
    )
    msg3 = _assistant("trailing")

    merged = _merge_adjacent_assistant([msg1, msg2, msg3])

    assert len(merged) == 1
    assert merged[0].reasoning_content == "deep thought"
    assert merged[0].reasoning_signature == "sig-xyz"


def test_non_adjacent_assistant_messages_unaffected() -> None:
    """Messages separated by a non-assistant message must not be merged."""
    user_msg = LLMMessage(role="user", content="hi")
    msg1 = _assistant("a", reasoning_content="r1", reasoning_signature="s1")
    msg2 = _assistant("b", reasoning_content="r2", reasoning_signature="s2")

    merged = _merge_adjacent_assistant([msg1, user_msg, msg2])

    assert len(merged) == 3
    assert merged[0].reasoning_content == "r1"
    assert merged[2].reasoning_content == "r2"
