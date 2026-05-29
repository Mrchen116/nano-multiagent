"""SSE wire-encoding helpers and hub re-exports for HTTP routes.

EventStreamHub and its supporting types live in agent.core.events.hub;
this module re-exports them for backward compatibility with any surviving
HTTP route code and provides the SSE wire-encoding utilities that are
purely HTTP-layer concerns (deleted together with the rest of http_api
in refactor-387-M4).
"""

from __future__ import annotations

import json
from typing import Any

# Re-export core pub/sub primitives so HTTP routes can import from one place.
from agent.core.events.hub import (  # noqa: F401
    EventStreamHub,
    StreamEvent,
    SubscriberOverflowError,
)


def encode_sse_event(*, sequence_num: int, event_id: str, event: str, data: dict[str, Any]) -> str:
    """Encode one event in SSE wire format expected by HTTP clients."""
    encoded_data = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return f"id: {sequence_num}\nevent: {event}\ndata: {encoded_data}\n\n"


def encode_sse_event_from_stream_event(stream_event: StreamEvent) -> str:
    """Encode a StreamEvent into SSE wire format."""
    return encode_sse_event(
        sequence_num=stream_event.sequence_num,
        event_id=stream_event.event_id,
        event=stream_event.event,
        data=stream_event.data,
    )


def encode_stream_error(
    *,
    session_id: str,
    run_id: str | None,
    code: str,
    message: str,
) -> bytes:
    """Encode a stream-level error frame (not published into hub)."""
    retryable = code == "subscriber_overflow"
    payload = {
        "event": "error",
        "session_id": session_id,
        "run_id": run_id,
        "code": code,
        "message": message,
        "retryable": retryable,
    }
    encoded_data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return f"event: error\ndata: {encoded_data}\n\n".encode()
