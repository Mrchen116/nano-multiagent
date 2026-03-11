"""Legacy compatibility facade for IM SSE helpers."""

from IM.infra.sse import encode_sse_event_frame, encode_sse_heartbeat

__all__ = ["encode_sse_event_frame", "encode_sse_heartbeat"]
