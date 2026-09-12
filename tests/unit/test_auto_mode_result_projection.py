"""Only explicitly projected, successful tool results inform auto approval."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agent.core.agent.loop import AgentLoop
from agent.core.agent.prompting import build_chat_messages
from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.core.types import Message
from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.builtins.auto_mode_gate import _build_transcript_user_message
from agent.platform.hooks.builtins.auto_mode_gate import build_transcript_entries
from tests.unit.test_auto_mode_gate_dispatch import _get_handler, _make_ctx


def test_only_a_later_native_human_reply_selects_recent_assistant_text() -> None:
    proposal = LLMMessage(
        role="assistant", content="OLD" + "x" * 2200 + "Push branch release?"
    )
    human = LLMMessage(
        role="user", content="yes", context_metadata={"context_origin": "human"}
    )
    event = LLMMessage(
        role="user", content="completed", context_metadata={"context_origin": "system"}
    )
    entries = build_transcript_entries([proposal, human])
    assert entries[0]["role"] == "assistant"
    text = entries[0]["content"][0]["text"]
    assert text.endswith("Push branch release?") and "OLD" not in text
    assert len(text) == 2000
    assert not any(
        e["role"] == "assistant"
        for e in build_transcript_entries([proposal, event, human])
    )
    assert not any(
        e["role"] == "assistant"
        for e in build_transcript_entries(
            [proposal, human], prior_assistant_context=False
        )
    )


def test_materialized_host_context_is_live_only_for_exact_runtime_record() -> None:
    from agent.core.agent.message_context import LiveToolContext

    ledger = LiveToolContext()
    history = _history("kernel")
    history[-1] = replace(
        history[-1],
        message_id="result-id",
        context_metadata={"host_classifier_context": "User: yes"},
    )
    ledger.register("result-id", "call-source", "User: yes")
    ctx = _context(
        history, Mock(side_effect=AssertionError("must not reproject history"))
    )
    ctx.metadata["_live_tool_context"] = ledger
    live = _build_transcript_user_message(ctx, "bash", "git push")
    assert '"host_context_live": "User: yes"' in live
    ledger.clear()
    restored = _build_transcript_user_message(ctx, "bash", "git push")
    assert '"host_context": "User: yes"' in restored
    assert "host_context_live" not in restored
    ledger.register("result-id", "call-source", "different text")
    assert "host_context_live" not in _build_transcript_user_message(
        ctx, "bash", "git push"
    )


def _history(format: str, *, error: bool = False) -> list:
    if format == "anthropic":
        return [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call-source",
                        "name": "source",
                        "input": {},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "surrounding user text"},
                    {
                        "type": "tool_result",
                        "tool_use_id": "call-source",
                        "content": "persisted result",
                        "is_error": error,
                    },
                ],
            },
        ]
    return [
        LLMMessage(
            role="assistant",
            content="do not trust assistant prose",
            tool_calls=(LLMToolCall(call_id="call-source", name="source"),),
        ),
        LLMMessage(
            role="tool",
            tool_call_id="call-source",
            content="persisted result",
            is_error=error,
        ),
    ]


def _context(history: list, projector=None):
    tools = {"source": SimpleNamespace()}
    if projector is not None:
        tools["source"].to_auto_classifier_result = projector
    return SimpleNamespace(
        message_history=history,
        metadata={"tool_registry": SimpleNamespace(get=tools.get)},
    )


@pytest.mark.parametrize("format", ["kernel", "anthropic"])
def test_explicit_projection_receives_actual_persisted_content(format: str) -> None:
    projector = Mock(return_value="User from conversation A: schedule the report")
    prompt = _build_transcript_user_message(
        _context(_history(format), projector), "scheduler", "add report job"
    )
    projector.assert_called_once_with("persisted result")
    assert "User from conversation A: schedule the report" in prompt
    assert "call-source" in prompt
    assert "persisted result" not in prompt
    assert "do not trust assistant prose" not in prompt
    if format == "anthropic":
        assert "surrounding user text" in prompt


@pytest.mark.parametrize("format", ["kernel", "anthropic"])
def test_existing_tools_and_error_results_stay_out(format: str) -> None:
    assert "persisted result" not in _build_transcript_user_message(
        _context(_history(format)), "scheduler", "add report job"
    )
    projector = Mock(return_value="must not authorize")
    prompt = _build_transcript_user_message(
        _context(_history(format, error=True), projector), "scheduler", "add report job"
    )
    projector.assert_not_called()
    assert "must not authorize" not in prompt


def test_results_match_prior_call_id_and_name_not_claimed_result_name() -> None:
    history = _history("kernel")
    history[-1] = replace(history[-1], tool_call_id="unknown", name="source")
    projector = Mock(return_value="must not authorize")
    _build_transcript_user_message(_context(history, projector), "scheduler", "add job")
    projector.assert_not_called()

    history = _history("kernel")
    history[0] = LLMMessage(
        role="assistant",
        content="",
        tool_calls=(LLMToolCall(call_id="call-source", name="legacy"),),
    )
    history[-1] = replace(history[-1], name="source")
    _build_transcript_user_message(_context(history, projector), "scheduler", "add job")
    projector.assert_not_called()


@pytest.mark.parametrize("replay", [False, True])
def test_failed_tool_result_remains_ineligible_in_live_and_replayed_history(
    replay: bool,
) -> None:
    persisted = Message(
        message_id="result",
        role="tool",
        tool_call_id="call-source",
        content="persisted result",
        metadata={"tool_error": "unavailable"},
    )
    result = (
        build_chat_messages(history_messages=(persisted,), user_text="next")[0]
        if replay
        else AgentLoop._build_llm_tool_result_message(None, persisted)
    )
    projector = Mock(return_value="must not authorize")
    _build_transcript_user_message(
        _context([_history("kernel")[0], result], projector), "scheduler", "add job"
    )
    assert result.is_error is True
    projector.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["raises", "invalid_type"])
async def test_projection_failure_blocks_before_classifier(failure: str) -> None:
    projector = (
        Mock(side_effect=ValueError("broken projection"))
        if failure == "raises"
        else Mock(return_value={"authorize": True})
    )
    ctx = _make_ctx(config=AutoModeConfig())
    ctx.message_history = _history("kernel")
    tools = {
        "source": SimpleNamespace(to_auto_classifier_result=projector),
        "scheduler": SimpleNamespace(
            to_auto_classifier_input=lambda _: "add report job"
        ),
    }
    ctx.metadata["tool_registry"] = SimpleNamespace(get=tools.get)
    ctx.call_model = AsyncMock()
    handler, _ = _get_handler()
    result = await handler({"name": "scheduler", "args": {}}, ctx)
    assert result["block"] is True
    assert "projection" in result["reason"]
    ctx.call_model.assert_not_called()
