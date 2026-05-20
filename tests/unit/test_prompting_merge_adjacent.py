"""RC2 regression: _merge_adjacent_assistant must preserve reasoning fields (bugfix-376).

Also covers _coalesce_assistant_group: same-group_id assistant Message rows must be
merged before build_chat_messages so parallel tool_use blocks restore correctly.
"""

from agent.core.agent.prompting import _merge_adjacent_assistant, _coalesce_assistant_group
from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.core.types import Message


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


# ---------------------------------------------------------------------------
# _coalesce_assistant_group tests
# ---------------------------------------------------------------------------

def _make_msg(
    message_id: str,
    role: str = "assistant",
    group_id: str | None = None,
    tool_calls: list | None = None,
    reasoning_content: str | None = None,
    reasoning_signature: str | None = None,
    content: str = "",
) -> Message:
    meta = {}
    if tool_calls:
        meta["tool_calls"] = tool_calls
    return Message(
        message_id=message_id,
        role=role,
        content=content,
        group_id=group_id,
        metadata=meta,
        reasoning_content=reasoning_content,
        reasoning_signature=reasoning_signature,
    )


def test_coalesce_same_group_id_merges_tool_calls() -> None:
    """Three assistant rows with the same group_id must collapse into one merged row."""
    tc1 = {"call_id": "tc1", "name": "read", "arguments": {}}
    tc2 = {"call_id": "tc2", "name": "read", "arguments": {}}
    tc3 = {"call_id": "tc3", "name": "read", "arguments": {}}
    msgs = (
        _make_msg("m1", group_id="g1", tool_calls=[tc1], reasoning_content="rc", reasoning_signature="sig"),
        _make_msg("m2", group_id="g1", tool_calls=[tc2]),
        _make_msg("m3", group_id="g1", tool_calls=[tc3]),
    )
    result = _coalesce_assistant_group(msgs)
    assert len(result) == 1
    assert result[0].metadata.get("tool_calls") == [tc1, tc2, tc3]
    assert result[0].reasoning_content == "rc"
    assert result[0].reasoning_signature == "sig"


def test_coalesce_different_group_ids_not_merged() -> None:
    """Rows with different group_ids must remain separate."""
    msgs = (
        _make_msg("m1", group_id="g1"),
        _make_msg("m2", group_id="g2"),
    )
    result = _coalesce_assistant_group(msgs)
    assert len(result) == 2


def test_coalesce_preserves_tool_rows() -> None:
    """tool rows interleaved with assistant rows must pass through unchanged."""
    tool_row = _make_msg("t1", role="tool", group_id="gt1")
    asst_row = _make_msg("a1", role="assistant", group_id="ga1")
    msgs = (asst_row, tool_row)
    result = _coalesce_assistant_group(msgs)
    assert len(result) == 2
    assert result[1].role == "tool"
