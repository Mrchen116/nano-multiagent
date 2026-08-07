#!/usr/bin/env python3
"""Minimal Anthropic-format SSE stub that records requests and returns ok text.

Use when a real Gateway / IM stack must complete agent turns without a live LLM
proxy, while still letting the test inspect every upstream request body
(messages / tools).

Each POST body is appended as one JSON line to ``NANO_FIXTURE_RECORD_PATH``
(required). The assistant text for the N-th request is ``ACK-<N>``.

Run::

    NANO_FIXTURE_RECORD_PATH=/tmp/llm.jsonl \\
      python3 scripts/fixtures/anthropic_sse_ok_recording.py 19995

Then point every ``llm.providers[].base_url`` in an isolated Gateway config at
``http://127.0.0.1:19995`` and start the real product entry.
"""

from __future__ import annotations

import http.server
import json
import os
import sys
import threading


def _sse_ok(
    text: str,
    *,
    message_start_usage: dict[str, object] | None,
    message_delta_usage: dict[str, object],
) -> bytes:
    message: dict[str, object] = {"role": "assistant", "content": []}
    if message_start_usage is not None:
        message["usage"] = message_start_usage
    frames = [
        {
            "event": "message_start",
            "data": {
                "type": "message_start",
                "message": message,
            },
        },
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
        {
            "event": "message_delta",
            "data": {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": message_delta_usage,
            },
        },
        {
            "event": "message_stop",
            "data": {"type": "message_stop"},
        },
    ]
    out = bytearray()
    for frame in frames:
        out.extend(
            f"event: {frame['event']}\r\ndata: {json.dumps(frame['data'])}\r\n\r\n".encode()
        )
    return bytes(out)


class _Handler(http.server.BaseHTTPRequestHandler):
    record_path: str = ""
    message_start_usage: dict[str, object] | None = None
    message_delta_usage: dict[str, object] = {"input_tokens": 1, "output_tokens": 1}
    _lock = threading.Lock()
    _count = 0

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            body = {"_raw": raw.decode("utf-8", errors="replace")}

        with self._lock:
            type(self)._count += 1
            n = type(self)._count
            with open(self.record_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(body, ensure_ascii=False) + "\n")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(
            _sse_ok(
                f"ACK-{n}",
                message_start_usage=self.message_start_usage,
                message_delta_usage=self.message_delta_usage,
            )
        )
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
    _Handler.message_start_usage = _read_usage_env("NANO_FIXTURE_MESSAGE_START_USAGE")
    _Handler.message_delta_usage = _read_usage_env(
        "NANO_FIXTURE_MESSAGE_DELTA_USAGE"
    ) or {"input_tokens": 1, "output_tokens": 1}
    # Truncate any prior run so callers can treat the file as this process's log.
    open(record_path, "w", encoding="utf-8").close()
    server = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    sys.stderr.write(
        f"anthropic_sse_ok_recording fixture listening on 127.0.0.1:{port} "
        f"record={record_path}\n"
    )
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def _read_usage_env(name: str) -> dict[str, object] | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{name} must encode a JSON object")
    return value


if __name__ == "__main__":
    sys.exit(main())
