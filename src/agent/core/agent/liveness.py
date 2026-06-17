"""Await-bound liveness heartbeat ticker (bugfix-417-M3 R3).

Two of the three "alive-but-quiet" windows the run can sit in produce no business
events on ``kernel.stream``: waiting for the (non-stream) LLM to return its first
chunk, and parking on a human permission decision. Both watchdogs (Gateway / IM)
judge liveness by the most recent stream event, so a long-but-live wait used to look
identical to a true stall and get reaped.

This module provides a ticker that runs ONLY while a specific await is in flight and
emits a ``run_heartbeat`` session event (the same event type the tool-execution
heartbeat publishes in R2) at an interval far below the watchdog timeout. The ticker
is await-bound: it starts before the await, stops the instant the await returns,
raises, or the run is cancelled — so the heartbeat proves *progress through this
wait*, never mere "the Task object still exists" (which would mask a real deadlock,
violating design decision 2's invariant).

Kept in ``core`` (no platform import): the caller injects a ``publish`` callable that
routes to the platform event hub via the hook context's session event publisher.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

# Heartbeat cadence for await-bound liveness. Must stay well below the consumer-side
# idle window (Gateway/IM default 120s) so jitter cannot trip a false reap; design
# decision 3 calls for ≤15s.
DEFAULT_LIVENESS_HEARTBEAT_INTERVAL_SECONDS = 10.0

PublishCallable = Callable[[str, Mapping[str, Any]], None]


async def _emit_liveness_heartbeats(
    *,
    publish: PublishCallable | None,
    run_id: str | None,
    source: str,
    interval: float = DEFAULT_LIVENESS_HEARTBEAT_INTERVAL_SECONDS,
) -> None:
    """Emit a run_heartbeat every ``interval`` seconds until cancelled.

    A no-op loop when ``publish`` or ``run_id`` is missing, so callers can create the
    task unconditionally. Publishing is fail-open: a publisher that raises (or is
    mid-teardown) must never bring down the awaited operation, so each emit is guarded.
    """
    if publish is None or not run_id:
        # Park until cancelled so the caller's create_task/cancel pairing still holds.
        while True:
            await asyncio.sleep(3600)
    while True:
        await asyncio.sleep(interval)
        try:
            publish(
                "run_heartbeat",
                {
                    "event": "run_heartbeat",
                    "run_id": run_id,
                    "source": source,
                },
            )
        except Exception:  # noqa: BLE001 — liveness must not crash the awaited op.
            # Drop this tick; the next business event or tick re-establishes liveness.
            continue


@contextlib.asynccontextmanager
async def liveness_ticker(
    *,
    publish: PublishCallable | None,
    run_id: str | None,
    source: str,
    interval: float = DEFAULT_LIVENESS_HEARTBEAT_INTERVAL_SECONDS,
) -> AsyncIterator[None]:
    """Run a background heartbeat ticker for the duration of the ``async with`` body.

    The ticker is cancelled (and drained) on exit regardless of how the body leaves —
    normal return, exception, or CancelledError — so it can never outlive the await it
    was guarding. A no-op when ``publish`` or ``run_id`` is missing (e.g. CLI without a
    session event hub), so callers need not branch on availability.

    Args:
        publish: ``(event_name, payload)`` callable routing to the session event hub.
        run_id: Run the heartbeat is attributed to; required to be useful.
        source: Liveness source tag (``"llm"`` / ``"permission"``) for observability.
        interval: Seconds between heartbeats; must be ≪ watchdog timeout.
    """
    if publish is None or not run_id:
        yield
        return
    task = asyncio.create_task(
        _emit_liveness_heartbeats(
            publish=publish, run_id=run_id, source=source, interval=interval
        )
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def _with_liveness_heartbeat(
    source_iter: AsyncIterator[Any],
    *,
    publish: PublishCallable | None,
    run_id: str | None,
    source: str,
    interval: float = DEFAULT_LIVENESS_HEARTBEAT_INTERVAL_SECONDS,
) -> AsyncIterator[Any]:
    """Re-yield an async iterator while a liveness ticker runs for its whole lifetime.

    Used to cover the LLM-await window (non-stream provider returns its single chunk
    after a long silence): the ticker fires run_heartbeat during the wait for each
    chunk and is torn down the moment iteration completes or raises (including the
    watchdog's own cancel). Transparent pass-through when no publisher/run_id.
    """
    async with liveness_ticker(
        publish=publish, run_id=run_id, source=source, interval=interval
    ):
        async for item in source_iter:
            yield item


def _broker_publish_adapter(publisher: Any) -> PublishCallable | None:
    """Adapt the permission broker's raw session event publisher to PublishCallable.

    The broker closure captures ``session_event_publisher`` directly (not a HookContext);
    returns ``None`` when absent so the permission ticker degrades to a no-op (e.g. CLI
    without an event hub).
    """
    if publisher is None:
        return None

    def _publish(event: str, data: Mapping[str, Any]) -> None:
        publisher(event, dict(data))

    return _publish


def session_event_publisher(hook_ctx: Any) -> PublishCallable | None:
    """Adapt a HookContext's session event publisher to the ticker's publish callable.

    Returns ``None`` when the context carries no publisher (e.g. a bare CLI context
    without an event hub) so the ticker degrades to a no-op rather than raising.
    """
    publisher = getattr(hook_ctx, "session_event_publisher", None)
    if publisher is None:
        return None

    def _publish(event: str, data: Mapping[str, Any]) -> None:
        publisher(event, dict(data))

    return _publish
