#!/usr/bin/env python3
"""Threaded, loopback-only HTTP faults for the real IM automatic-review journey.

The owning test supplies an isolated record path and terminates this process.
Requests use RETRY_CASE=<policy>-<fault> markers; no runtime knobs are changed.
"""

from __future__ import annotations

import http.server
import json
import os
import re
import socket
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

from anthropic_sse_tool_approval_recording import (
    _frames_bytes,
    _message_end,
    _message_start,
    _sse_text,
)


def _tool(case: str) -> bytes:
    return _frames_bytes(
        [
            _message_start(),
            {
                "event": "content_block_start",
                "data": {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "tool_use",
                        "id": f"retry-{case}",
                        "name": "bash",
                        "input": {},
                    },
                },
            },
            {
                "event": "content_block_delta",
                "data": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(
                            {
                                "description": "Record one isolated test effect",
                                "command": f"printf '%s\\n' 'effect:{case}' >> retry-{case}.txt",
                            }
                        ),
                    },
                },
            },
            {
                "event": "content_block_stop",
                "data": {"type": "content_block_stop", "index": 0},
            },
            *_message_end("tool_use"),
        ]
    )


class Handler(http.server.BaseHTTPRequestHandler):
    """Serve faults from actual HTTP without exposing credentials in records."""

    counts: dict[tuple[str, str], int] = {}
    lock = threading.Lock()
    record_path = ""

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"review fixture ready")

    def do_POST(self) -> None:  # noqa: N802
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = json.loads(raw or b"{}")
        markers = re.findall(r"RETRY_CASE=([a-z0-9-]+)", json.dumps(body))
        case = markers[-1] if markers else "missing"
        policy, _, kind = case.partition("-")
        reviewer = body.get("model") == "review"
        key = (case, "review" if reviewer else "main")
        with self.lock:
            self.counts[key] = count = self.counts.get(key, 0) + 1
            with open(self.record_path, "a", encoding="utf-8") as record:
                record.write(
                    json.dumps(
                        {
                            "case": case,
                            "kind": key[1],
                            "ordinal": count,
                            "time": time.time(),
                            "session": self.headers.get("x-agent-session-id"),
                            "request": body,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        if case == "missing":
            self.send_error(400, "missing case marker")
            return
        if not reviewer:
            response = _tool(case) if count == 1 else _sse_text(f"ACK:{case}")
        else:
            if policy == "nano" and (
                kind in {"stage2-service", "stage2-timeout"}
                and count == 1
                or kind == "stage-exhaust"
                and count == 3
            ):
                self.respond(
                    _sse_text("<block>yes</block><reason>need second stage</reason>")
                )
                return
            if kind == "config-request" and count == 1:
                time.sleep(2)
            if kind == "stage2-timeout" and count == 2:
                time.sleep(65)
            if kind == "transport" and count == 1:
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            if kind == "cancel" or kind == "timeout" and count == 1:
                time.sleep(95 if policy == "codex" else 35)
            if (
                kind in {"auth", "persistent"}
                or count == 1
                and kind
                in {
                    "service",
                    "rate",
                    "rate-date",
                    "long",
                    "mixed",
                    "cancel-backoff",
                    "config-backoff",
                }
                or kind == "stage2-service"
                and count == 2
                or kind == "stage-exhaust"
                and count in {1, 2, 4}
            ):
                status = (
                    401
                    if kind == "auth"
                    else 429
                    if kind.startswith("rate") or kind == "long"
                    else 503
                )
                delay = (
                    "15"
                    if kind == "long"
                    else "2"
                    if kind in {"cancel-backoff", "config-backoff"}
                    else "1"
                )
                if kind == "rate-date":
                    delay = format_datetime(
                        datetime.now(UTC) + timedelta(seconds=2), usegmt=True
                    )
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Retry-After", delay)
                self.send_header("request-id", f"{case}-{count}")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "type": "error",
                            "error": {
                                "type": "authentication_error"
                                if status == 401
                                else "rate_limit_error"
                                if status == 429
                                else "overloaded_error",
                                "message": "controlled HTTP failure",
                            },
                        }
                    ).encode()
                )
                return
            malformed = (
                kind == "invalid"
                or kind == "format"
                and count == 1
                or kind == "mixed"
                and count == 2
            )
            verdict = (
                "malformed verdict"
                if malformed
                else "<block>no</block>"
                if policy == "nano"
                else '{"outcome":"allow"}'
            )
            response = _sse_text(verdict)
        self.respond(response)

    def respond(self, response: bytes) -> None:
        """Write a complete SSE response, allowing expected late cancellation."""
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(response)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # A cancelled/expired request deliberately leaves a late response.

    def log_message(self, _format: str, *args: object) -> None:
        pass


def main() -> int:
    Handler.record_path = os.environ.get("NANO_FIXTURE_RECORD_PATH", "")
    if not Handler.record_path:
        sys.stderr.write("NANO_FIXTURE_RECORD_PATH is required\n")
        return 2
    server = http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler)
    server.daemon_threads = True
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
