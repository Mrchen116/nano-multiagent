"""In-memory pub/sub event hub with bounded history replay semantics.

This module is the permanent home of EventStreamHub, StreamEvent, and
SubscriberOverflowError.  Moved here from agent.platform.http_api.sse in
refactor-387-M4 because these are process-internal pub/sub primitives
with no HTTP dependency — the SSE wire-encoding helpers (encode_sse_event,
encode_stream_error) stayed in http_api and were deleted with it.
"""

from __future__ import annotations

import asyncio
import json
import queue
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any, AsyncIterator, Iterator

from agent.core.ids import make_event_id


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """Canonical event payload stored in the stream history."""

    sequence_num: int
    event_id: str
    event: str
    session_id: str
    created_at: str
    data: dict[str, Any]


class SubscriberOverflowError(Exception):
    """Raised when a subscriber's queue overflows and events are being dropped."""


@dataclass(slots=True)
class _Subscriber:
    queue: queue.Queue[StreamEvent]
    session_id: str | None
    overflow_marked: bool = False


class EventStreamHub:
    """Publish/subscribe hub for session and global event streams.

    Notes:
        The hub keeps a bounded history for late subscribers and isolates slow
        subscribers by dropping events when their queue is full.
    """

    def __init__(self, *, history_limit: int = 2000) -> None:
        self._history_limit = history_limit
        self._history: list[StreamEvent] = []
        self._subscribers: list[_Subscriber] = []
        self._lock = Lock()
        self._next_sequence_num: int = 1

    def publish(
        self,
        *,
        event: str,
        session_id: str,
        data: dict[str, Any],
    ) -> StreamEvent:
        """Publish one event and fan out to matching subscribers.

        Args:
            event: Event name.
            session_id: Session scope for routing and replay filtering.
            data: JSON-serializable event payload.

        Returns:
            Stored `StreamEvent` with generated id/timestamp.
        """
        payload = dict(data)
        payload.setdefault("event", event)
        payload.setdefault("session_id", session_id)

        with self._lock:
            sequence_num = self._next_sequence_num
            self._next_sequence_num += 1
            stream_event = StreamEvent(
                sequence_num=sequence_num,
                event_id=make_event_id(),
                event=event,
                session_id=session_id,
                created_at=_utc_now_iso(),
                data=payload,
            )
            self._history.append(stream_event)
            if len(self._history) > self._history_limit:
                overflow = len(self._history) - self._history_limit
                del self._history[:overflow]
            subscribers = tuple(self._subscribers)

        for subscriber in subscribers:
            if subscriber.session_id is not None and subscriber.session_id != session_id:
                continue
            try:
                subscriber.queue.put_nowait(stream_event)
            except queue.Full:
                subscriber.overflow_marked = True
                continue
        return stream_event

    def stream(
        self,
        *,
        session_id: str | None,
        after_sequence: int,
        max_events: int,
        timeout_seconds: float,
    ) -> Iterator[StreamEvent]:
        """Yield events after sequence number followed by live events.

        Args:
            session_id: Session filter; `None` subscribes to global stream.
            after_sequence: Only yield events with sequence_num greater than this.
            max_events: Maximum number of events yielded in this poll window.
            timeout_seconds: Long-poll timeout for waiting on new events.
        """
        buffer: queue.Queue[StreamEvent] = queue.Queue(maxsize=max_events * 2 + 8)
        subscriber = _Subscriber(queue=buffer, session_id=session_id)

        with self._lock:
            history_cut = len(self._history)
            self._subscribers.append(subscriber)
            history = [
                event
                for event in self._history[:history_cut]
                if event.sequence_num > after_sequence
                and (session_id is None or event.session_id == session_id)
            ]

        yielded = 0
        try:
            for event in history:
                yield event
                yielded += 1
                if yielded >= max_events:
                    return

            deadline = time.monotonic() + timeout_seconds
            while yielded < max_events:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                try:
                    event = buffer.get(timeout=remaining)
                except queue.Empty:
                    return
                yield event
                yielded += 1
        finally:
            with self._lock:
                self._subscribers = [item for item in self._subscribers if item is not subscriber]

    def current_sequence(self) -> int:
        """Return the last published sequence atomically; used as anchor for POST."""
        with self._lock:
            return self._next_sequence_num - 1

    def has_sequence(self, sequence_num: int) -> bool:
        """Return True if events after sequence_num are replayable from history."""
        with self._lock:
            if not self._history:
                return sequence_num < self._next_sequence_num
            return sequence_num >= self._history[0].sequence_num - 1

    async def stream_session(
        self,
        *,
        session_id: str,
        after_sequence: int,
        tick_seconds: float = 1.0,
        max_empty_ticks: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Long-lived session-scoped stream.

        Behavior:
          - Replays history events with sequence > after_sequence (subject to history_limit).
          - Then switches to real-time queue.
          - Does NOT close on terminal run_status — keeps yielding until caller cancels.
          - On subscriber overflow, raises SubscriberOverflowError; caller emits
            stream-level error frame and closes.

        Args:
            max_empty_ticks: When given, the stream closes after this many consecutive
                empty queue polls.  Used only by tests; production callers leave it
                as ``None`` for a truly persistent stream.
        """
        buffer: queue.Queue[StreamEvent] = queue.Queue(maxsize=256)
        subscriber = _Subscriber(queue=buffer, session_id=session_id)

        with self._lock:
            self._subscribers.append(subscriber)
            history = [
                event
                for event in self._history
                if event.sequence_num > after_sequence and event.session_id == session_id
            ]

        empty_ticks = 0
        try:
            for event in history:
                if subscriber.overflow_marked:
                    raise SubscriberOverflowError()
                yield event

            while True:
                if subscriber.overflow_marked:
                    raise SubscriberOverflowError()
                try:
                    event = buffer.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(tick_seconds)
                    if subscriber.overflow_marked:
                        raise SubscriberOverflowError()
                    if max_empty_ticks is not None:
                        empty_ticks += 1
                        if empty_ticks >= max_empty_ticks:
                            return
                    continue
                empty_ticks = 0
                yield event
        finally:
            with self._lock:
                self._subscribers = [item for item in self._subscribers if item is not subscriber]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
