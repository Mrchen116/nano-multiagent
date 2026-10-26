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


def _tool(case: str, name: str = "bash", arguments: dict | None = None) -> bytes:
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
                        "id": f"retry-{case}" if name == "bash" else f"{name}-{case}",
                        "name": name,
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
                            arguments
                            if arguments is not None
                            else {
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


def _pending_tool(body: dict) -> str | None:
    """Locate only the explicit pending action, not its historical tool catalog."""
    text = "\n".join(
        block.get("text", "")
        for message in body.get("messages", [])[-1:]
        for block in message.get("content", [])
        if isinstance(block, dict)
    )
    planned = re.search(r"<planned_action>(.*?)</planned_action>", text, re.S)
    if planned:
        return json.loads(planned[1]).get("name")
    for line in reversed(text.splitlines()):
        if line.startswith("{"):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in row:
                return next((key for key in row if key != "id"), None)
    return None


class Handler(http.server.BaseHTTPRequestHandler):
    """Serve faults from actual HTTP without exposing credentials in records."""

    counts: dict[tuple[str, str], int] = {}
    main_sessions: dict[str, str] = {}
    session_counts: dict[tuple[str, str, str], int] = {}
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
        pending_tool = _pending_tool(body) if reviewer else None
        session = self.headers.get("x-agent-session-id", "missing")
        with self.lock:
            self.counts[key] = count = self.counts.get(key, 0) + 1
            session_key = (case, session, key[1])
            self.session_counts[session_key] = per_session = (
                self.session_counts.get(session_key, 0) + 1
            )
            if not reviewer:
                self.main_sessions.setdefault(case, session)
            with open(self.record_path, "a", encoding="utf-8") as record:
                record.write(
                    json.dumps(
                        {
                            "case": case,
                            "kind": key[1],
                            "ordinal": count,
                            "time": time.time(),
                            "session": session,
                            "pending_tool": pending_tool,
                            "request": body,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        if case == "missing":
            # A Global native wake must acquire the true human message through Inbox.
            # Do not inject a human source or call RuntimeClient from the fixture.
            if not reviewer:
                targets = re.findall(
                    r'"target"\s*:\s*"(c_[a-z0-9]+)"',
                    json.dumps(body).replace('\\"', '"'),
                )
                args = (
                    {"action": "read", "target": targets[-1]}
                    if targets
                    else {"action": "check"}
                )
                self.respond(_tool("bootstrap", "inbox", args))
            else:
                self.send_error(400, "missing case marker")
            return
        if not reviewer:
            if kind.startswith("route-"):
                self.respond(
                    self.route_response(case, kind, body, session, per_session)
                )
                return
            response = _tool(case) if count == 1 else _sse_text(f"ACK:{case}")
        else:
            if kind.startswith("route-") and pending_tool != "bash":
                self.respond(
                    _sse_text(
                        "<block>no</block>"
                        if policy == "nano"
                        else '{"outcome":"allow"}'
                    )
                )
                return
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
                or kind.startswith("route-")
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

    def route_response(
        self, case: str, kind: str, body: dict, session: str, ordinal: int
    ) -> bytes:
        """Request actual native child/timer tools; never synthesize their sources."""
        target = re.findall(r"TARGET=(c_[a-z0-9]+)", json.dumps(body))[-1]
        if kind == "route-child":
            if session == self.main_sessions[case]:
                return (
                    _tool(
                        case,
                        "subagent",
                        {
                            "description": "Review a delegated effect",
                            "prompt": f"CHILD RETRY_CASE={case} TARGET={target} Execute one test effect; never retry a blocked tool.",
                            "run_in_background": False,
                        },
                    )
                    if ordinal == 1
                    else _sse_text(f"ACK:{case}")
                )
            return _tool(case) if ordinal == 1 else _sse_text(f"CHILD_ACK:{case}")
        if kind.startswith("route-heartbeat"):
            if ordinal == 1:
                return _sse_text(f"READY:{case}")
            return _tool(case) if ordinal == 2 else _sse_text(f"ACK:{case}")
        if kind.startswith("route-schedule"):
            if ordinal == 1:
                return _tool(
                    case,
                    "schedule_create",
                    {
                        "title": f"Scheduled effect {case}",
                        "prompt": f"SCHEDULE_EXEC RETRY_CASE={case} TARGET={target} Execute one test effect, no repeat.",
                        "after_seconds": 2,
                    },
                )
            if ordinal == 2:
                return _sse_text(f"REGISTERED:{case}")
            return _tool(case) if ordinal == 3 else _sse_text(f"ACK:{case}")
        if ordinal == 1:
            return _tool(case)
        if kind == "route-global" and ordinal == 2:
            return _tool(
                case, "send_message", {"target": target, "text": f"ACK:{case}"}
            )
        return _sse_text(f"ACK:{case}")

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
