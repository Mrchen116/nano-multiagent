#!/usr/bin/env python3
"""Hold model responses while real group messages invalidate pending sends."""

from __future__ import annotations

import http.server
import json
import os
import re
import sys
import threading

from anthropic_sse_collaboration_recording import _json_result, _results, _text, _tool
from anthropic_sse_tool_approval_recording import _sse_text


class Handler(http.server.BaseHTTPRequestHandler):
    record_path = os.environ["NANO_FIXTURE_RECORD_PATH"]
    lock = threading.Lock()
    gates = {key: threading.Event() for key in ["A:0", "B:0", "C:0", "D:0", "D:1"]}
    pending: set[str] = set()

    def do_GET(self) -> None:  # noqa: N802
        with self.lock:
            payload = json.dumps(sorted(self.pending)).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/release/"):
            self.gates[self.path.removeprefix("/release/")].set()
            self.send_response(200)
            self.end_headers()
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        guardian = any(
            tool["name"].startswith("guardian_") for tool in body.get("tools", [])
        )
        role = re.search(r"COUNTING_AGENT ([ABCD])", _text(body.get("system", [])))
        with self.lock:
            with open(self.record_path, "a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "role": role[1] if role else None,
                            "guardian": guardian,
                            "request": body,
                        }
                    )
                    + "\n"
                )
        try:
            response = (
                _sse_text('{"outcome":"allow"}')
                if guardian
                else self.count(body, role[1])
            )
        except (ValueError, KeyError, TypeError) as error:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"error": {"type": "invalid_request_error", "message": str(error)}}
                ).encode()
            )
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(response)

    def count(self, body: dict, role: str) -> bytes:
        results = _results(body)
        if "check" not in results:
            return _tool("check", "inbox", {"action": "check"})
        target = _json_result(results, "check")["sources"][0]["target"]
        for round_number in range(3):
            read = f"read-{round_number}"
            draft = f"draft-{round_number}"
            if read not in results:
                if round_number:
                    target = _json_result(results, f"draft-{round_number - 1}")[
                        "inbox_targets"
                    ][0]
                return _tool(read, "inbox", {"action": "read", "target": target})
            if draft not in results:
                numbers = [
                    int(text)
                    for index in range(round_number + 1)
                    for message in _json_result(results, f"read-{index}")["messages"]
                    if (text := _text(message["content"]).strip()).isdigit()
                ]
                key = f"{role}:{round_number}"
                if key in self.gates:
                    with self.lock:
                        self.pending.add(key)
                    if not self.gates[key].wait(60):
                        raise ValueError(f"unreleased model response: {key}")
                return _tool(
                    draft,
                    "send_message",
                    {"target": target, "text": str(max(numbers, default=0) + 1)},
                )
            status = _json_result(results, draft)["status"]
            if status == "sent":
                return _sse_text("Done.")
            if status != "held_for_revalidation":
                raise ValueError(f"unexpected send status: {status}")
        raise ValueError("unexpected fourth draft")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


if __name__ == "__main__":
    with open(Handler.record_path, "w", encoding="utf-8"):
        pass
    http.server.ThreadingHTTPServer(
        ("127.0.0.1", int(sys.argv[1])), Handler
    ).serve_forever()
