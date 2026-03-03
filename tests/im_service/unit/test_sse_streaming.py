"""Unit tests for IM SSE frame encoding helpers."""

import json

from IM.sse import encode_sse_event_frame, encode_sse_heartbeat


def test_encode_sse_event_frame_contains_id_event_data() -> None:
    """Render one SSE event frame with id/event/data lines and trailing blank line."""
    payload = {"message_id": "msg-1", "delivery_status": "sent"}

    frame = encode_sse_event_frame(event_id=12, event_type="message.sent", data=payload)

    assert frame.startswith("id: 12\n")
    assert "event: message.sent\n" in frame
    assert f"data: {json.dumps(payload, separators=(",", ":"), ensure_ascii=True)}\n" in frame
    assert frame.endswith("\n\n")


def test_encode_sse_heartbeat_uses_comment_frame() -> None:
    """Render SSE heartbeat as comment frame to keep connection alive."""
    assert encode_sse_heartbeat() == ": keepalive\n\n"
