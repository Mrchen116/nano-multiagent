"""Background SSE session event subscriber for per-session background events.

After the main per-turn SSE loop terminates, background hooks (e.g. self_improvement)
may still publish session events (e.g. self_evolution_review) seconds to minutes later.
This module maintains a persistent, per-session SSE subscriber that receives those
events and routes them to a caller-supplied callback.

Architecture:
- One ``BackgroundSessionEventSubscriber`` per kernel session.
- Runs as an asyncio background task; never blocks the inbound pipeline.
- Reconnects on stream errors with configurable backoff.
- Only the caller-supplied ``on_event`` callback decides what to do with each event;
  this module applies no business logic.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

_log = logging.getLogger(__name__)

# Session-level event names that should be forwarded to the callback.
# All other events (run_status, assistant_message, etc.) are ignored.
_SESSION_EVENT_NAMES = frozenset({"self_evolution_review"})


class BackgroundSessionEventSubscriber:
    """Maintain a persistent SSE subscription for one kernel session.

    Receives session-level events (e.g. ``self_evolution_review``) that arrive
    after the main per-turn SSE loop has terminated and invokes ``on_event`` for
    each matching event.

    Args:
        kernel_client: Client exposing ``stream_session(session_id, last_event_id, workspace_root)``.
        session_id: Kernel session to subscribe to.
        on_event: Async callback invoked for each matching session event.
        after_sequence: Stream starting sequence (last sequence seen by main loop).
        reconnect_delay: Base delay (seconds) before reconnect on stream error.
        max_reconnect_delay: Maximum backoff delay (seconds).
        event_filter: Set of event names to forward; defaults to session event names.
        workspace_root: Forwarded to stream_session so the stateless kernel can locate
            the session JSONL (Refs #64 — session is per-workspace_root scoped).
    """

    def __init__(
        self,
        *,
        kernel_client: Any,
        session_id: str,
        on_event: Callable[[Mapping[str, Any]], Awaitable[None]],
        after_sequence: int = 0,
        reconnect_delay: float = 2.0,
        max_reconnect_delay: float = 60.0,
        event_filter: frozenset[str] = _SESSION_EVENT_NAMES,
        workspace_root: str | None = None,
    ) -> None:
        self._kernel_client = kernel_client
        self._session_id = session_id
        self._on_event = on_event
        self._after_sequence = after_sequence
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._event_filter = event_filter
        # workspace_root is forwarded to stream_session so the stateless kernel can
        # locate the session JSONL (Refs #64 — session is per-workspace_root scoped).
        self._workspace_root = workspace_root
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the background subscription task."""
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run_loop(),
            name=f"bg-sse-sub:{self._session_id}",
        )

    async def stop(self) -> None:
        """Stop the background subscription and wait for the task to finish."""
        self._stop_event.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    async def _run_loop(self) -> None:
        """Reconnect-loop: re-establish SSE stream on error, stop when event is set."""
        delay = self._reconnect_delay
        last_sequence = self._after_sequence

        while not self._stop_event.is_set():
            try:
                async for event in self._kernel_client.stream_session(
                    session_id=self._session_id,
                    last_event_id=last_sequence if last_sequence > 0 else None,
                    workspace_root=self._workspace_root,  # Refs #64
                ):
                    if self._stop_event.is_set():
                        return
                    # Track sequence for reconnect replay.
                    seq = event.get("_id") or event.get("sequence_num")
                    if isinstance(seq, int):
                        last_sequence = max(last_sequence, seq)
                    event_name = event.get("event")
                    if event_name in self._event_filter:
                        try:
                            await self._on_event(event)
                        except Exception:
                            _log.warning(
                                "background session event callback error",
                                exc_info=True,
                                extra={
                                    "session_id": self._session_id,
                                    "event": event_name,
                                },
                            )
                # Stream ended cleanly — treat as transient; reconnect after delay.
                delay = self._reconnect_delay
            except asyncio.CancelledError:
                return
            except Exception:
                _log.debug(
                    "background SSE stream error; reconnecting in %.1fs",
                    delay,
                    exc_info=True,
                    extra={"session_id": self._session_id},
                )

            if self._stop_event.is_set():
                return
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._stop_event.wait()),
                    timeout=delay,
                )
                # stop_event was set during sleep
                return
            except asyncio.TimeoutError:
                pass
            delay = min(delay * 2, self._max_reconnect_delay)
