"""Tests for _merge_adjacent_assistant in prompting module."""

from agent.core.agent.prompting import _merge_adjacent_assistant
from agent.core.llm.interfaces import LLMMessage, LLMToolCall


def test_merge_two_adjacent_assistant_text_messages() -> None:
    messages = [
        LLMMessage(role="assistant", content="Hello "),
        LLMMessage(role="assistant", content="world"),
    ]
    result = _merge_adjacent_assistant(messages)
    assert len(result) == 1
    assert result[0].role == "assistant"
    assert result[0].content == "Hello world"


def test_merge_assistant_with_tool_calls() -> None:
    messages = [
        LLMMessage(role="assistant", content="我来分析", tool_calls=()),
        LLMMessage(
            role="assistant",
            content="",
            tool_calls=(
                LLMToolCall(call_id="call_1", name="Read", arguments={"path": "/tmp/foo"}),
            ),
        ),
    ]
    result = _merge_adjacent_assistant(messages)
    assert len(result) == 1
    assert result[0].role == "assistant"
    assert result[0].content == "我来分析"
    assert len(result[0].tool_calls) == 1
    assert result[0].tool_calls[0].name == "Read"


def test_does_not_merge_non_adjacent_assistant() -> None:
    messages = [
        LLMMessage(role="assistant", content="first"),
        LLMMessage(role="tool", content="result", tool_call_id="call_1"),
        LLMMessage(role="assistant", content="second"),
    ]
    result = _merge_adjacent_assistant(messages)
    assert len(result) == 3
    assert result[0].content == "first"
    assert result[1].role == "tool"
    assert result[2].content == "second"


def test_empty_list() -> None:
    assert _merge_adjacent_assistant([]) == []


def test_single_message() -> None:
    messages = [LLMMessage(role="assistant", content="only")]
    result = _merge_adjacent_assistant(messages)
    assert len(result) == 1
    assert result[0].content == "only"


def test_merge_preserves_tool_calls_across_multiple_blocks() -> None:
    messages = [
        LLMMessage(role="assistant", content="text1", tool_calls=()),
        LLMMessage(
            role="assistant",
            content="",
            tool_calls=(LLMToolCall(call_id="c1", name="Read", arguments={}),),
        ),
        LLMMessage(
            role="assistant",
            content="text2",
            tool_calls=(LLMToolCall(call_id="c2", name="Write", arguments={}),),
        ),
    ]
    result = _merge_adjacent_assistant(messages)
    assert len(result) == 1
    assert result[0].content == "text1text2"
    assert len(result[0].tool_calls) == 2
    assert result[0].tool_calls[0].name == "Read"
    assert result[0].tool_calls[1].name == "Write"


def test_does_not_merge_user_messages() -> None:
    messages = [
        LLMMessage(role="user", content="hi"),
        LLMMessage(role="user", content="there"),
    ]
    result = _merge_adjacent_assistant(messages)
    assert len(result) == 2
    assert result[0].content == "hi"
    assert result[1].content == "there"
