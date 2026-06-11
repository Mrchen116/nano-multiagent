"""Retry wrapper for LLM clients that handles transient failures transparently."""

import asyncio
from collections.abc import AsyncIterator

from agent.core.errors import ModelError

from .interfaces import LLMClient, LLMGenerateRequest, LLMMessage

# Delays cycle through these values; after every _COOLDOWN_EVERY consecutive
# failures an extra _COOLDOWN_SECONDS pause is inserted before resuming.
_BACKOFF_DELAYS = (0.5, 1.0, 2.0)
_MAX_RETRIES = 20
_COOLDOWN_EVERY = 5
_COOLDOWN_SECONDS = 30.0


class RetryingLLMClient:
    """LLMClient decorator that retries transient failures with exponential back-off.

    Only retryable ModelErrors are retried; non-retryable errors propagate immediately.
    Retries are transparent to callers — the wrapped client's generate() is called
    again with the identical request until it succeeds or retries are exhausted.

    Partial-content invariant: once any message has been yielded downstream, a
    mid-stream failure is NOT retried in-place.  Re-sending the whole request
    would make the agent loop repeat already-yielded / already-persisted content,
    causing transcript corruption.  The error is re-raised as-is so the caller
    can decide how to handle it (typically: write an error marker and surface the
    failure to the user without duplicating the partial response).

    Exhaustion semantics: when the retry budget is exhausted, the last real
    provider error is preserved — its message, code/type/status and raw_body are
    kept intact.  Only the retry bookkeeping metadata (retry_exhausted, attempts,
    delay) is appended to details, so the user sees the actual upstream reason.
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        backoff_index = 0
        for attempt in range(_MAX_RETRIES + 1):
            yielded_content = False
            try:
                async for msg in self._client.generate(request):
                    yielded_content = True
                    yield msg
                return
            except ModelError as exc:
                if not exc.retryable:
                    raise
                # Partial-content guard: do not retry in-place after the caller
                # has already received output — re-sending would duplicate content.
                if yielded_content:
                    raise
                if attempt >= _MAX_RETRIES:
                    # Preserve the last real provider error; append retry metadata.
                    merged_details = dict(exc.details)
                    merged_details["retry_exhausted"] = True
                    merged_details["attempts"] = attempt + 1
                    merged_details["delay"] = _BACKOFF_DELAYS[
                        backoff_index % len(_BACKOFF_DELAYS)
                    ]
                    raise ModelError(
                        exc.message,
                        retryable=False,
                        details=merged_details,
                    ) from exc
                delay = _BACKOFF_DELAYS[backoff_index]
                backoff_index = (backoff_index + 1) % len(_BACKOFF_DELAYS)
                await self._sleep(delay)
                failed_attempts = attempt + 1
                if failed_attempts % _COOLDOWN_EVERY == 0:
                    backoff_index = 0
                    await self._sleep(_COOLDOWN_SECONDS)

        raise AssertionError("unreachable")  # pragma: no cover

    async def _sleep(self, seconds: float) -> None:
        """Extracted for test monkeypatching."""
        await asyncio.sleep(seconds)
