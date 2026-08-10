#!/usr/bin/env python3
"""Controlled OpenAI-compatible fixture for self-evolution product journeys.

The server routes responses only from explicit scenario state, per-scenario request
index, message roles, and tool-call/result structure. It never inspects prompt text.
Its control/state endpoints are fixture-only positive evidence that a private review
branch really executed; user-visible assertions still come from the real IM relay.
"""

from __future__ import annotations

import http.server
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

_FOREGROUND_NO_SAVE = "FOREGROUND-NO-SAVE-COMPLETE"
_FOREGROUND_NO_SAVE_SEED = "FOREGROUND-NO-SAVE-SEED"
_RAW_NO_SAVE = "Nothing to save."
_CLASSIFIER_ALLOW = "<block>no</block>"


class _ScenarioState:
    def __init__(self, record_path: Path) -> None:
        self._record_path = record_path
        self._lock = threading.Lock()
        self.scenario = "idle"
        self.agent_request_index = 0
        self.requests: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    def control(self, payload: dict[str, Any]) -> dict[str, Any]:
        scenario = payload.get("scenario")
        if not isinstance(scenario, str) or not scenario:
            raise ValueError("control requires a non-empty scenario")
        with self._lock:
            self.scenario = scenario
            if payload.get("reset") is True:
                self.agent_request_index = 0
                self.requests = []
                self.events = []
                self._record_path.write_text("", encoding="utf-8")
            return self.snapshot_unlocked()

    def classify(self, body: dict[str, Any]) -> dict[str, Any]:
        tools = body.get("tools")
        roles = [
            message.get("role")
            for message in body.get("messages", [])
            if isinstance(message, dict)
        ]
        tool_result_ids = [
            str(message.get("tool_call_id"))
            for message in body.get("messages", [])
            if isinstance(message, dict)
            and message.get("role") == "tool"
            and message.get("tool_call_id")
        ]
        tool_names = [
            str(item.get("function", {}).get("name"))
            for item in tools or []
            if isinstance(item, dict)
            and isinstance(item.get("function"), dict)
            and item["function"].get("name")
        ]
        with self._lock:
            if not tools:
                kind = "classifier"
                routing_basis = "structural_no_tools"
                request_index = None
            else:
                self.agent_request_index += 1
                request_index = self.agent_request_index
                if self.scenario == "no_save" and request_index <= 2:
                    kind = "foreground"
                else:
                    kind = "review"
                routing_basis = "scenario_request_index"
            summary = {
                "scenario": self.scenario,
                "kind": kind,
                "routing_basis": routing_basis,
                "request_index": request_index,
                "roles": roles,
                "tool_names": tool_names,
                "tool_result_ids": tool_result_ids,
            }
            self.requests.append(summary)
            with self._record_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(summary, ensure_ascii=False) + "\n")
            return dict(summary)

    def add_event(self, event: str, **data: object) -> None:
        with self._lock:
            self.events.append({"event": event, **data})

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self.snapshot_unlocked()

    def snapshot_unlocked(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "agent_request_index": self.agent_request_index,
            "requests": [dict(item) for item in self.requests],
            "events": [dict(item) for item in self.events],
        }


def _sse_text(text: str) -> bytes:
    return _sse_frames(
        (
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": text},
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {"index": 0, "delta": {}, "finish_reason": "stop"}
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )
    )


def _sse_frames(frames: tuple[dict[str, Any], ...]) -> bytes:
    chunks = [f"data: {json.dumps(frame, separators=(',', ':'))}\n\n" for frame in frames]
    chunks.append("data: [DONE]\n\n")
    return "".join(chunks).encode("utf-8")


class _Handler(http.server.BaseHTTPRequestHandler):
    state: _ScenarioState

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/state":
            self.send_error(404)
            return
        self._send_json(200, self.state.snapshot())

    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json()
        if self.path == "/control":
            try:
                state = self.state.control(payload)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, state)
            return
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return

        request = self.state.classify(payload)
        scenario = request["scenario"]
        kind = request["kind"]
        if kind == "classifier":
            body = _sse_text(_CLASSIFIER_ALLOW)
        elif scenario == "no_save" and request["request_index"] == 1:
            body = _sse_text(_FOREGROUND_NO_SAVE_SEED)
        elif scenario == "no_save" and request["request_index"] == 2:
            body = _sse_text(_FOREGROUND_NO_SAVE)
        elif scenario == "no_save" and kind == "review":
            self.state.add_event("no_save_review_completed")
            body = _sse_text(_RAW_NO_SAVE)
        else:
            self._send_json(
                409,
                {
                    "error": "unexpected controlled request state",
                    "scenario": scenario,
                    "kind": kind,
                    "request_index": request["request_index"],
                },
            )
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def main() -> int:
    record_path_raw = os.environ.get("NANO_FIXTURE_RECORD_PATH", "").strip()
    if not record_path_raw:
        sys.stderr.write("NANO_FIXTURE_RECORD_PATH is required\n")
        return 2
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 19996
    record_path = Path(record_path_raw)
    record_path.write_text("", encoding="utf-8")
    _Handler.state = _ScenarioState(record_path)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    sys.stderr.write(
        f"openai self-evolution fixture listening on 127.0.0.1:{port} "
        f"record={record_path}\n"
    )
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
