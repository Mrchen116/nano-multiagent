"""Tests for RetryingLLMClient retry semantics.

bugfix-402-M2:
1. Partial-content guard: once any message is yielded, mid-stream failure
   must NOT be retried in-place (would cause duplicate output).
2. Exhaustion preservation: when retries are exhausted, the raised error
   must carry the last real provider error message/details, not a generic
   "exceeded N retries" wrapper.
3. Retry-exhausted metadata: the raised error must include retry_exhausted=True
   and attempts count in its details.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.llm.retry import RetryingLLMClient


def _make_request() -> LLMGenerateRequest:
    return LLMGenerateRequest(
        session_id="sess-retry-test",
        model="test-model",
        messages=(LLMMessage(role="user", content="ping"),),
    )


async def _collect(
    client: RetryingLLMClient, request: LLMGenerateRequest
) -> list[LLMMessage]:
    msgs: list[LLMMessage] = []
    async for msg in client.generate(request):
        msgs.append(msg)
    return msgs


# ---------------------------------------------------------------------------
# Partial-content guard
# ---------------------------------------------------------------------------


class _YieldThenFailClient:
    """Yields some content then raises a retryable error."""

    def __init__(self, *, fail_message: str = "mid-stream disconnect") -> None:
        self.call_count = 0
        self._fail_message = fail_message

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.call_count += 1
        yield LLMMessage(role="assistant", content="partial content")
        raise ModelError(self._fail_message, retryable=True)


async def test_mid_stream_failure_after_content_is_not_retried() -> None:
    """Once content is yielded, mid-stream failure must not trigger a retry."""
    inner = _YieldThenFailClient()
    client = RetryingLLMClient(inner)
    client._sleep = lambda _s: __import__("asyncio").sleep(0)  # type: ignore[assignment]

    with pytest.raises(ModelError) as exc_info:
        await _collect(client, _make_request())

    # Exactly 1 attempt — no retry after content was yielded
    assert inner.call_count == 1, (
        f"Expected 1 call (no retry after partial content), got {inner.call_count}"
    )
    # Error is the real upstream error, not a wrapper
    assert exc_info.value.message == "mid-stream disconnect", (
        f"Expected original error message, got: {exc_info.value.message!r}"
    )
    # Still retryable=True (caller can decide to discard and restart)
    assert exc_info.value.retryable is True


async def test_mid_stream_failure_does_not_duplicate_yielded_content() -> None:
    """Content yielded before failure is not repeated on a second attempt."""
    inner = _YieldThenFailClient()
    client = RetryingLLMClient(inner)
    client._sleep = lambda _s: __import__("asyncio").sleep(0)  # type: ignore[assignment]

    messages: list[LLMMessage] = []
    with pytest.raises(ModelError):
        async for msg in client.generate(_make_request()):
            messages.append(msg)

    content_messages = [m for m in messages if m.content]
    assert len(content_messages) == 1, (
        f"Partial content must appear exactly once, got {len(content_messages)}: {content_messages}"
    )


# ---------------------------------------------------------------------------
# No-content-yet: retries still happen
# ---------------------------------------------------------------------------


class _FailNTimesClient:
    """Raises a retryable error N times then succeeds without yielding prior."""

    def __init__(self, *, fail_count: int) -> None:
        self.call_count = 0
        self._fail_count = fail_count

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.call_count += 1
        if self.call_count <= self._fail_count:
            raise ModelError(f"attempt {self.call_count} failed", retryable=True)
        yield LLMMessage(role="assistant", content="success")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


async def test_pre_content_retryable_errors_are_retried() -> None:
    """Errors before any content is yielded should be retried per budget."""
    inner = _FailNTimesClient(fail_count=2)
    client = RetryingLLMClient(inner)

    async def _no_sleep(_s: float) -> None:
        pass

    client._sleep = _no_sleep  # type: ignore[assignment]

    messages = await _collect(client, _make_request())
    assert inner.call_count == 3, (
        f"Expected 3 attempts (2 failures + 1 success), got {inner.call_count}"
    )
    assert any(m.content == "success" for m in messages)


# ---------------------------------------------------------------------------
# Exhaustion: preserve real error
# ---------------------------------------------------------------------------


class _AlwaysFailClient:
    """Always raises a retryable error with a distinctive message."""

    def __init__(
        self, *, error_message: str = "real provider error: quota exceeded"
    ) -> None:
        self.call_count = 0
        self._error_message = error_message
        self._last_details: dict = {"provider_code": "quota_exceeded", "status": 429}

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.call_count += 1
        if False:
            yield LLMMessage(role="assistant", content="")
        raise ModelError(
            self._error_message,
            retryable=True,
            details=self._last_details,
        )


async def test_exhaustion_preserves_original_error_message() -> None:
    """After retries exhausted, raised error must carry last real provider message."""
    from agent.core.llm.retry import _MAX_RETRIES

    inner = _AlwaysFailClient(error_message="quota exceeded: billing cycle limit")
    client = RetryingLLMClient(inner)

    async def _no_sleep(_s: float) -> None:
        pass

    client._sleep = _no_sleep  # type: ignore[assignment]

    with pytest.raises(ModelError) as exc_info:
        await _collect(client, _make_request())

    err = exc_info.value
    # Must NOT be a "exceeded N retries" wrapper message
    assert "exceeded" not in err.message.lower() or "quota" in err.message.lower(), (
        f"Expected original provider message, got: {err.message!r}"
    )
    assert "quota exceeded" in err.message, (
        f"Original message must be preserved, got: {err.message!r}"
    )


async def test_exhaustion_adds_retry_metadata_in_details() -> None:
    """Exhausted error details must include retry_exhausted=True and attempts count."""
    from agent.core.llm.retry import _MAX_RETRIES

    inner = _AlwaysFailClient()
    client = RetryingLLMClient(inner)

    async def _no_sleep(_s: float) -> None:
        pass

    client._sleep = _no_sleep  # type: ignore[assignment]

    with pytest.raises(ModelError) as exc_info:
        await _collect(client, _make_request())

    details = exc_info.value.details
    assert details.get("retry_exhausted") is True, (
        f"details must contain retry_exhausted=True, got: {details}"
    )
    assert "attempts" in details, f"details must contain 'attempts', got: {details}"
    assert details["attempts"] == _MAX_RETRIES + 1, (
        f"attempts should be {_MAX_RETRIES + 1}, got: {details['attempts']}"
    )


async def test_exhaustion_preserves_original_details() -> None:
    """Exhausted error must retain original provider details alongside retry metadata."""
    inner = _AlwaysFailClient(error_message="rate limit hit")
    client = RetryingLLMClient(inner)

    async def _no_sleep(_s: float) -> None:
        pass

    client._sleep = _no_sleep  # type: ignore[assignment]

    with pytest.raises(ModelError) as exc_info:
        await _collect(client, _make_request())

    details = exc_info.value.details
    # Original provider details must be preserved
    assert details.get("provider_code") == "quota_exceeded", (
        f"Original provider_code must be preserved, got: {details}"
    )
    assert details.get("status") == 429, (
        f"Original status must be preserved, got: {details}"
    )
    # Retry metadata appended
    assert details.get("retry_exhausted") is True
