"""Compatibility shim for the canonical platform HTTP API SSE hub."""

from nano_multiagent.platform.http_api.sse import EventStreamHub, StreamEvent, encode_sse_event

__all__ = ["EventStreamHub", "StreamEvent", "encode_sse_event"]
