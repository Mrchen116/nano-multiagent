"""SSE frame encoding helpers for IM conversation event streams."""

import json
from typing import Mapping


def encode_sse_event_frame(*, event_id: int, event_type: str, data: Mapping[str, object]) -> str:
    """Encode one SSE event frame with id/event/data fields.

    Args:
        event_id: Monotonic event id used by clients for reconnect cursors.
        event_type: Logical event name such as message.sent.
        data: JSON-serializable event payload.

    Returns:
        Encoded SSE frame ending with a blank line separator.
    """
    payload = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"


def encode_sse_heartbeat() -> str:
    """Encode a keepalive SSE comment frame."""
    return ": keepalive\n\n"
