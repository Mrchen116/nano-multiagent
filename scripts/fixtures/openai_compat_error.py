#!/usr/bin/env python3
"""HTTP stub that emits an OpenAI-compatible top-level `{"error":{...}}` SSE frame.

Wire-protocol detail::

    data: {"error":{"type":"rate_limit_error","message":"..."}}

Note: OpenAI-compat clients (kernel's OpenAICompatClient) check for the
top-level "error" key OUTSIDE the "choices" array. The frame must NOT include
"choices" or the client treats it as a normal delta.

Run::

    python3 scripts/fixtures/openai_compat_error.py 19999
"""

from __future__ import annotations

import http.server
import json
import sys


ERROR_PAYLOAD = {
    "error": {
        "type": "rate_limit_error",
        "message": "rate limit exceeded - openai_compat_error.py fixture (refactor-381)",
    },
}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        chunk = (f"data: {json.dumps(ERROR_PAYLOAD)}\r\n\r\n").encode("utf-8")
        self.wfile.write(chunk)
        self.wfile.flush()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 19999
    server = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    sys.stderr.write(f"openai_compat_error fixture listening on 127.0.0.1:{port}\n")
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
