"""In-memory SSE event hub with bounded history replay semantics."""

from __future__ import annotations

import json
import queue
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Iterator

from nano_multiagent.core.ids import make_event_id


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """Canonical SSE event payload stored in stream history."""

    event_id: str
    event: str
    session_id: str
    created_at: str
    data: dict[str, Any]


@dataclass(slots=True)
class _Subscriber:
    queue: queue.Queue[StreamEvent]
    session_id: str | None


class EventStreamHub:
    """Publish/subscribe hub for session and global SSE HTTP endpoints.

    Notes:
        The hub keeps a bounded history for late subscribers and isolates slow
        subscribers by dropping events when their queue is full.
    """

    def __init__(self, *, history_limit: int = 2000) -> None:
        self._history_limit = history_limit
        self._history: list[StreamEvent] = []
        self._subscribers: list[_Subscriber] = []
        self._lock = Lock()

    def publish(
        self,
        *,
        event: str,
        session_id: str,
        data: dict[str, Any],
    ) -> StreamEvent:
        """Publish one event and fan out to matching subscribers.

        Args:
            event: Event name used by SSE `event:` field.
            session_id: Session scope for routing and replay filtering.
            data: JSON-serializable event payload.

        Returns:
            Stored `StreamEvent` with generated id/timestamp.
        """
        payload = dict(data)
        payload.setdefault("event", event)
        payload.setdefault("session_id", session_id)
        stream_event = StreamEvent(
            event_id=make_event_id(),
            event=event,
            session_id=session_id,
            created_at=_utc_now_iso(),
            data=payload,
        )

        with self._lock:
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
                continue
        return stream_event

    def stream(
        self,
        *,
        session_id: str | None,
        max_events: int,
        timeout_seconds: float,
    ) -> Iterator[StreamEvent]:
        """Yield history replay followed by live events for one subscriber.

        Args:
            session_id: Session filter; `None` subscribes to global stream.
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
                if session_id is None or event.session_id == session_id
            ]

        yielded = 0
        try:
            for event in history[-max_events:]:
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


def encode_sse_event(*, event_id: str, event: str, data: dict[str, Any]) -> str:
    """Encode one event in SSE wire format expected by HTTP clients."""
    encoded_data = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return f"id: {event_id}\nevent: {event}\ndata: {encoded_data}\n\n"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
