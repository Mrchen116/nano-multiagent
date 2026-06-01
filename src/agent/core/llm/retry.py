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
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        backoff_index = 0
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async for msg in self._client.generate(request):
                    yield msg
                return
            except ModelError as exc:
                if not exc.retryable:
                    raise
                if attempt >= _MAX_RETRIES:
                    raise ModelError(
                        f"LLM generate exceeded {_MAX_RETRIES} retries: {exc.message}",
                        retryable=False,
                        details=exc.details,
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
