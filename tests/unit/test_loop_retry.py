"""Tests for AgentLoop.run() error propagation (retry removed in M251).

Retry logic previously lived inside loop.py but was removed; errors now
propagate immediately. Retry is handled at a higher layer if needed.
"""

import pytest

from collections.abc import AsyncIterator

from agent.core.errors import ModelError
from agent.core.agent.loop import AgentLoop
from agent.core.agent.runtime import build_turn_result
from agent.core.agent.state import AgentState
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage


async def _run_loop(loop: AgentLoop, state: AgentState):
    """Consume AgentLoop async generator and build TurnResult."""
    messages = []
    async for msg in loop.run(state):
        messages.append(msg)
    return build_turn_result(state.session_id, state.turn_id, messages)


class _CountingLLMClient:
    """LLM client stub that raises retryable errors N times then succeeds."""

    def __init__(self, *, fail_count: int) -> None:
        self.call_count = 0
        self._fail_count = fail_count

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.call_count += 1
        if self.call_count <= self._fail_count:
            raise ModelError("upstream blip", retryable=True)
        response = LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="ok"),
            finish_reason="stop",
        )
        yield response.message
        yield LLMMessage(
            role="assistant",
            content="",
            finish_reason=response.finish_reason,
            usage=response.usage,
        )


class _AlwaysRetryableLLMClient:
    """LLM client stub that always raises retryable ModelError."""

    def __init__(self) -> None:
        self.call_count = 0

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        if False:
            yield LLMMessage(role="assistant", content="")
        self.call_count += 1
        raise ModelError("always fails", retryable=True)


class _NonRetryableErrorLLMClient:
    """LLM client stub that immediately raises non-retryable ModelError."""

    def __init__(self) -> None:
        self.call_count = 0

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        if False:
            yield LLMMessage(role="assistant", content="")
        self.call_count += 1
        raise ModelError("fatal error", retryable=False)


def _make_state(*, session_id: str = "sess-retry-unit", user_text: str = "ping") -> AgentState:
    return AgentState(
        session_id=session_id,
        turn_id="turn-retry-unit",
        turn_count=1,
        history_messages=(),
        input_parts=(),
        user_text=user_text,
    )


async def test_loop_propagates_retryable_error_immediately() -> None:
    """Loop does NOT retry; retryable errors propagate on first call."""
    llm = _CountingLLMClient(fail_count=2)
    loop = AgentLoop(llm_client=llm, model="test-model")
    state = _make_state()

    with pytest.raises(ModelError) as exc_info:
        await _run_loop(loop, state)

    assert llm.call_count == 1
    assert exc_info.value.retryable is True


async def test_loop_propagates_single_retryable_error_immediately() -> None:
    """Loop does NOT retry; exactly 1 call is made before error propagates."""
    llm = _CountingLLMClient(fail_count=1)
    loop = AgentLoop(llm_client=llm, model="test-model")
    state = _make_state()

    with pytest.raises(ModelError) as exc_info:
        await _run_loop(loop, state)

    assert llm.call_count == 1
    assert exc_info.value.retryable is True


async def test_loop_propagates_always_retryable_error() -> None:
    """Loop does NOT retry; always-failing retryable errors propagate as-is."""
    llm = _AlwaysRetryableLLMClient()
    loop = AgentLoop(llm_client=llm, model="test-model")
    state = _make_state()

    with pytest.raises(ModelError) as exc_info:
        await _run_loop(loop, state)

    assert exc_info.value.retryable is True
    assert llm.call_count == 1


async def test_loop_non_retryable_error_propagates_immediately() -> None:
    """Non-retryable ModelError propagates on first attempt without retry."""
    llm = _NonRetryableErrorLLMClient()
    loop = AgentLoop(llm_client=llm, model="test-model")
    state = _make_state()

    with pytest.raises(ModelError) as exc_info:
        await _run_loop(loop, state)

    assert exc_info.value.retryable is False
    # Only 1 call — no retry for non-retryable
    assert llm.call_count == 1


async def test_loop_zero_retryable_failures_calls_generate_once() -> None:
    """When first call succeeds, generate() is called exactly once."""
    llm = _CountingLLMClient(fail_count=0)
    loop = AgentLoop(llm_client=llm, model="test-model")
    state = _make_state()

    result = await _run_loop(loop, state)

    assert llm.call_count == 1
    assert result.completed is True
