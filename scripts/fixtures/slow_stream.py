#!/usr/bin/env python3
"""HTTP stub that opens an SSE stream then hangs (or closes mid-stream).

Use to drive the "stream ended without terminal event" path
(``ModelError(retryable=True)``) in AnthropicClient / OpenAICompatClient.

Modes:
- ``hang``: write nothing, hold socket open forever (triggers read timeout)
- ``truncate``: write a partial content_block_start frame then close socket
  before message_stop arrives

Run::

    python3 scripts/fixtures/slow_stream.py 19996 truncate
"""

from __future__ import annotations

import http.server
import sys
import time


def _build_handler(mode: str) -> type[http.server.BaseHTTPRequestHandler]:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            if mode == "truncate":
                self.wfile.write(
                    b'event: message_start\r\ndata: {"type":"message_start","message":{"role":"assistant"}}\r\n\r\n'
                )
                self.wfile.flush()
                time.sleep(0.2)
                # Close abruptly — no message_stop, no content_block_stop.
                return

            # hang mode: write nothing, hold the socket open until the client times out.
            time.sleep(60)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    return _Handler


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: slow_stream.py <port> [hang|truncate]\n")
        return 2
    port = int(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "truncate"
    if mode not in {"hang", "truncate"}:
        sys.stderr.write(f"unknown mode: {mode}\n")
        return 2
    server = http.server.HTTPServer(("127.0.0.1", port), _build_handler(mode))
    sys.stderr.write(f"slow_stream fixture listening on 127.0.0.1:{port} (mode={mode})\n")
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
