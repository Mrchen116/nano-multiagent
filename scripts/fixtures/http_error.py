#!/usr/bin/env python3
"""HTTP stub that returns a configurable status code (4xx / 5xx).

Use to drive ``ModelError`` paths that go through ``raise_for_status()`` —
HTTP 401 (auth), 429 (rate limit), 500 (provider crash), 503 (overloaded).

Run::

    python3 scripts/fixtures/http_error.py 19997 429
    python3 scripts/fixtures/http_error.py 19997 500

Body is JSON shaped like the matching provider's error envelope so error
messages flowing through to the user bubble look realistic.
"""

from __future__ import annotations

import http.server
import json
import sys


_MESSAGES = {
    401: ("authentication_error", "invalid api key - http_error.py fixture"),
    403: ("permission_error", "forbidden - http_error.py fixture"),
    429: ("rate_limit_error", "rate limit exceeded - http_error.py fixture"),
    500: ("api_error", "internal server error - http_error.py fixture"),
    502: ("api_error", "bad gateway - http_error.py fixture"),
    503: ("overloaded_error", "service unavailable - http_error.py fixture"),
}


def _build_handler(status_code: int) -> type[http.server.BaseHTTPRequestHandler]:
    err_type, err_msg = _MESSAGES.get(status_code, ("api_error", f"http {status_code}"))
    body = json.dumps(
        {"type": "error", "error": {"type": err_type, "message": err_msg}}
    )

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    return _Handler


def main() -> int:
    if len(sys.argv) < 3:
        sys.stderr.write("usage: http_error.py <port> <status_code>\n")
        return 2
    port = int(sys.argv[1])
    status_code = int(sys.argv[2])
    server = http.server.HTTPServer(("127.0.0.1", port), _build_handler(status_code))
    sys.stderr.write(
        f"http_error fixture listening on 127.0.0.1:{port} (status={status_code})\n"
    )
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
