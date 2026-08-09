#!/usr/bin/env python3
"""Drive one deterministic tool -> compact -> continue -> restart journey."""

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


def _message_start(input_tokens: int) -> dict[str, Any]:
    return {
        "event": "message_start",
        "data": {
            "type": "message_start",
            "message": {
                "role": "assistant",
                "content": [],
                "usage": {"input_tokens": input_tokens},
            },
        },
    }


def _message_end(stop_reason: str) -> list[dict[str, Any]]:
    return [
        {
            "event": "message_delta",
            "data": {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason},
                "usage": {"output_tokens": 1},
            },
        },
        {"event": "message_stop", "data": {"type": "message_stop"}},
    ]


def _sse_text(text: str, *, input_tokens: int) -> bytes:
    return _frames_bytes(
        [
            _message_start(input_tokens),
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
    )


def _sse_read_call() -> bytes:
    arguments = json.dumps({"path": "compaction-source.txt"})
    return _frames_bytes(
        [
            _message_start(100),
            {
                "event": "content_block_start",
                "data": {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "tool_use",
                        "id": "compaction-read-1",
                        "name": "read",
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
    )


def _tool_pair_ids(body: dict[str, Any]) -> tuple[set[str], set[str]]:
    calls: set[str] = set()
    results: set[str] = set()
    for message in body.get("messages") or []:
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                calls.add(str(block.get("id") or ""))
            elif block.get("type") == "tool_result":
                results.add(str(block.get("tool_use_id") or ""))
    return calls, results


def _has_tool_result(body: dict[str, Any]) -> bool:
    return bool(_tool_pair_ids(body)[1])


def _is_summary_request(body: dict[str, Any]) -> bool:
    return "Your task is to create a detailed summary" in json.dumps(
        body.get("messages") or [], ensure_ascii=False
    )


class _Handler(http.server.BaseHTTPRequestHandler):
    record_path = ""
    sentinel = ""
    _lock = threading.Lock()
    _summary_completed = False
    _post_summary_count = 0

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")

        with self._lock:
            if _is_summary_request(body):
                kind = "summary"
            elif _has_tool_result(body):
                kind = "tool_followup"
            elif not body.get("tools"):
                kind = "classifier"
            elif self._summary_completed:
                kind = "post_summary"
            else:
                kind = "tool_call"
            with open(self.record_path, "a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps({"kind": kind, "request": body}, ensure_ascii=False)
                    + "\n"
                )

            if kind == "summary":
                calls, results = _tool_pair_ids(body)
                valid = (
                    calls == results == {"compaction-read-1"}
                    and self.sentinel in json.dumps(body, ensure_ascii=False)
                )
                if not valid:
                    self.send_error(422, "summary request lost tool pairing or objective")
                    return
                type(self)._summary_completed = True
                summary = (
                    "<analysis>validated tool history</analysis>\n"
                    "<summary>\n"
                    f"1. Primary Request and Intent: preserve {self.sentinel}.\n"
                    "2. Key Technical Concepts: context compaction and tool pairing.\n"
                    "7. Pending Tasks: continue the original objective.\n"
                    "8. Current Work: the source file was read successfully.\n"
                    "</summary>"
                )
                response = _sse_text(summary, input_tokens=100)
            elif kind == "tool_followup":
                response = _sse_text(
                    f"TOOL-COMPLETE {self.sentinel}", input_tokens=45_000
                )
            elif kind == "classifier":
                response = _sse_text("<block>no</block>", input_tokens=100)
            elif kind == "post_summary":
                type(self)._post_summary_count += 1
                prefix = (
                    "CONTINUED" if self._post_summary_count == 1 else "RESTARTED"
                )
                response = _sse_text(f"{prefix} {self.sentinel}", input_tokens=100)
            else:
                response = _sse_read_call()

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
    sentinel = os.environ.get("NANO_FIXTURE_SENTINEL", "").strip()
    if not record_path or not sentinel:
        sys.stderr.write("NANO_FIXTURE_RECORD_PATH and NANO_FIXTURE_SENTINEL are required\n")
        return 2
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 19995
    _Handler.record_path = record_path
    _Handler.sentinel = sentinel
    with open(record_path, "w", encoding="utf-8"):
        pass
    server = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    sys.stderr.write(
        f"compaction fixture listening on 127.0.0.1:{port} record={record_path}\n"
    )
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
