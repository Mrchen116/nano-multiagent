#!/usr/bin/env python3
"""Record Anthropic requests and deterministically drive one approval tool loop."""

from __future__ import annotations

import http.server
import json
import os
import sys
import threading
from typing import Any


def _frames_bytes(frames: list[dict[str, Any]]) -> bytes:
    output = bytearray()
    for frame in frames:
        output.extend(
            f"event: {frame['event']}\r\ndata: {json.dumps(frame['data'])}\r\n\r\n".encode()
        )
    return bytes(output)


def _message_start() -> dict[str, Any]:
    return {
        "event": "message_start",
        "data": {
            "type": "message_start",
            "message": {"role": "assistant", "content": []},
        },
    }


def _message_end(stop_reason: str) -> list[dict[str, Any]]:
    return [
        {
            "event": "message_delta",
            "data": {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason},
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        },
        {"event": "message_stop", "data": {"type": "message_stop"}},
    ]


def _sse_text(text: str) -> bytes:
    frames = [
        _message_start(),
        {
            "event": "content_block_start",
            "data": {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        },
        {
            "event": "content_block_delta",
            "data": {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text},
            },
        },
        {
            "event": "content_block_stop",
            "data": {"type": "content_block_stop", "index": 0},
        },
        *_message_end("end_turn"),
    ]
    return _frames_bytes(frames)


def _sse_tool_call(sequence: int) -> bytes:
    arguments = json.dumps(
        {
            "path": f"approval-route-{sequence}.txt",
            "content": f"approval-route-{sequence}",
        }
    )
    frames = [
        _message_start(),
        {
            "event": "content_block_start",
            "data": {
                "type": "content_block_start",
                "index": 0,
                "content_block": {
                    "type": "tool_use",
                    "id": f"tool-{sequence}",
                    "name": "write",
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
                    "partial_json": arguments,
                },
            },
        },
        {
            "event": "content_block_stop",
            "data": {"type": "content_block_stop", "index": 0},
        },
        *_message_end("tool_use"),
    ]
    return _frames_bytes(frames)


def _is_classifier(body: dict[str, Any]) -> bool:
    return (
        "automated security classifier"
        in json.dumps(body.get("system", ""), ensure_ascii=False).lower()
    )


def _last_message_has_tool_result(body: dict[str, Any]) -> bool:
    messages = body.get("messages") or []
    if not messages or not isinstance(messages[-1], dict):
        return False
    content = messages[-1].get("content")
    return isinstance(content, list) and any(
        isinstance(block, dict) and block.get("type") == "tool_result"
        for block in content
    )


class _Handler(http.server.BaseHTTPRequestHandler):
    record_path = ""
    failing_model = "approval-fail"
    _lock = threading.Lock()
    _count = 0

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        body = json.loads(raw.decode("utf-8") or "{}")
        classifier = _is_classifier(body)

        with self._lock:
            type(self)._count += 1
            sequence = type(self)._count
            kind = "classifier" if classifier else "normal"
            with open(self.record_path, "a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps({"kind": kind, "request": body}, ensure_ascii=False)
                    + "\n"
                )

        if classifier:
            response = _sse_text(
                "unparseable classifier response"
                if body.get("model") == self.failing_model
                else "<block>no</block>"
            )
        elif _last_message_has_tool_result(body):
            response = _sse_text(f"ACK-{sequence}")
        else:
            response = _sse_tool_call(sequence)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(response)
        self.wfile.flush()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def main() -> int:
    record_path = os.environ.get("NANO_FIXTURE_RECORD_PATH", "").strip()
    if not record_path:
        sys.stderr.write("NANO_FIXTURE_RECORD_PATH is required\n")
        return 2
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 19995
    _Handler.record_path = record_path
    with open(record_path, "w", encoding="utf-8"):
        pass
    server = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    sys.stderr.write(
        f"tool approval fixture listening on 127.0.0.1:{port} record={record_path}\n"
    )
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
