"""Tests for AgentLoop.run() internal retry on retryable ModelError.

Retry logic lives inside loop.py wrapping only LLMClient.generate();
session history writes are not repeated on retry.
"""

import pytest

from agent.core.errors import ModelError
from agent.core.agent.loop import AgentLoop
from agent.core.agent.state import AgentState
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage


class _CountingLLMClient:
    """LLM client stub that raises retryable errors N times then succeeds."""

    def __init__(self, *, fail_count: int) -> None:
        self.call_count = 0
        self._fail_count = fail_count

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.call_count += 1
        if self.call_count <= self._fail_count:
            raise ModelError("upstream blip", retryable=True)
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="ok"),
            finish_reason="stop",
        )


class _AlwaysRetryableLLMClient:
    """LLM client stub that always raises retryable ModelError."""

    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.call_count += 1
        raise ModelError("always fails", retryable=True)


class _NonRetryableErrorLLMClient:
    """LLM client stub that immediately raises non-retryable ModelError."""

    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
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


async def test_loop_retries_generate_on_retryable_error_and_succeeds() -> None:
    """Loop retries generate() internally when retryable and succeeds without raising."""
    llm = _CountingLLMClient(fail_count=2)
    loop = AgentLoop(llm_client=llm, model="test-model")
    state = _make_state()

    result = await loop.run(state)

    # 2 failures + 1 success = 3 calls total
    assert llm.call_count == 3
    assert result.completed is True
    assert result.stop_reason == "stop"
    assert result.messages[0].content == "ok"


async def test_loop_single_retryable_failure_then_success() -> None:
    """Loop handles exactly 1 retryable failure then succeeds."""
    llm = _CountingLLMClient(fail_count=1)
    loop = AgentLoop(llm_client=llm, model="test-model")
    state = _make_state()

    result = await loop.run(state)

    assert llm.call_count == 2
    assert result.completed is True


async def test_loop_max_retries_raises_non_retryable_model_error() -> None:
    """After max_retries exhausted, loop raises non-retryable ModelError."""
    llm = _AlwaysRetryableLLMClient()
    loop = AgentLoop(llm_client=llm, model="test-model")
    state = _make_state()

    with pytest.raises(ModelError) as exc_info:
        await loop.run(state)

    assert exc_info.value.retryable is False
    # Must have attempted max_retries+1 times (initial + retries)
    assert llm.call_count > 1


async def test_loop_non_retryable_error_propagates_immediately() -> None:
    """Non-retryable ModelError propagates on first attempt without retry."""
    llm = _NonRetryableErrorLLMClient()
    loop = AgentLoop(llm_client=llm, model="test-model")
    state = _make_state()

    with pytest.raises(ModelError) as exc_info:
        await loop.run(state)

    assert exc_info.value.retryable is False
    # Only 1 call — no retry for non-retryable
    assert llm.call_count == 1


async def test_loop_zero_retryable_failures_calls_generate_once() -> None:
    """When first call succeeds, generate() is called exactly once."""
    llm = _CountingLLMClient(fail_count=0)
    loop = AgentLoop(llm_client=llm, model="test-model")
    state = _make_state()

    result = await loop.run(state)

    assert llm.call_count == 1
    assert result.completed is True
