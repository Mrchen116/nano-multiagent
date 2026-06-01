#!/usr/bin/env python3
"""Minimal HTTP stub that emits an Anthropic-format SSE `error` event.

Use when you need to drive nano-multiagent's "LLM upstream error → user-readable"
path (bugfix-380) end-to-end without burning real provider quota or rigging a
flaky proxy.

Wire-protocol detail this stub gets right (and why ad-hoc桩 typically don't):

    event: error
    data: {"type":"error","error":{"type":"overloaded_error","message":"..."}}

Both the `event:` line and the `data:` JSON `"type":"error"` field are required;
the kernel's AnthropicClient._stream_response keys on event_type=="error".
Omit either and you fall through to "stream ended without terminal event"
(retryable=True) — that path triggers a 20-retry storm and you'll think the
fix is broken when really the桩 is wrong.

Run::

    python3 scripts/fixtures/anthropic_sse_error.py 19998

Then point the kernel at it::

    NANO_MULTIAGENT_LLM_PROVIDER=anthropic \
    NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:19998 \
    PYTHONPATH=src python -m uvicorn agent.platform.http_api.app:app --port 8000

Triggering a request gets you a `retryable=False` ModelError within ~1 second.
"""

from __future__ import annotations

import http.server
import json
import sys


ERROR_PAYLOAD = {
    "type": "error",
    "error": {
        "type": "overloaded_error",
        "message": "model overloaded - anthropic_sse_error.py fixture (refactor-381)",
    },
}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        # Drain request body so the client side does not error on EPIPE.
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        chunk = (f"event: error\r\ndata: {json.dumps(ERROR_PAYLOAD)}\r\n\r\n").encode(
            "utf-8"
        )
        self.wfile.write(chunk)
        self.wfile.flush()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        # Quieter default; uncomment for debugging.
        return


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 19998
    server = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    sys.stderr.write(f"anthropic_sse_error fixture listening on 127.0.0.1:{port}\n")
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
