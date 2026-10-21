#!/usr/bin/env python3
"""Serve deterministic review failures through real Anthropic HTTP in an isolated stack.

Only fixture inputs are recorded. No production credentials or configuration are read.
Start with --port 0 --ready-file PATH --record PATH; POST /control selects a
scenario, and GET /records exposes controlled request facts and reviewer prompts.
The output is local evidence, not safe for publication without separate review.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time

from auto_review_source_scenario import source_blocks


def frames(blocks: list[dict]) -> bytes:
    """Encode a complete Anthropic streamed message with real text/tool blocks."""
    events = [
        (
            "message_start",
            {
                "message": {
                    "id": "fixture",
                    "type": "message",
                    "role": "assistant",
                    "model": "fixture",
                    "content": [],
                    "usage": {"input_tokens": 20, "output_tokens": 0},
                }
            },
        )
    ]
    tools = False
    for index, block in enumerate(blocks):
        original = block
        if block["type"] == "tool_use":
            tools = True
            block = {**block, "input": {}}
        events.append(("content_block_start", {"index": index, "content_block": block}))
        if block["type"] == "tool_use":
            events.append(
                (
                    "content_block_delta",
                    {
                        "index": index,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": json.dumps(original["input"]),
                        },
                    },
                )
            )
        events.append(("content_block_stop", {"index": index}))
    events += [
        (
            "message_delta",
            {
                "delta": {"stop_reason": "tool_use" if tools else "end_turn"},
                "usage": {"output_tokens": 5},
            },
        ),
        ("message_stop", {}),
    ]
    return "".join(
        f"event: {kind}\ndata: {json.dumps({'type': kind, **data})}\n\n"
        for kind, data in events
    ).encode()


def tool(name: str, arguments: dict, call_id: str) -> dict:
    """Return a protocol-native tool block, never an internal runtime command."""
    return {"type": "tool_use", "id": call_id, "name": name, "input": arguments}


class Handler(BaseHTTPRequestHandler):
    """Hold independent scenario counters under one lock for concurrent requests."""

    lock = threading.Lock()
    scenarios: dict[str, dict] = {}
    records: list[dict] = []
    record: Path
    protocol_version = "HTTP/1.1"

    def respond(
        self, status: int, data: bytes, content_type="application/json", headers=None
    ):
        """Send bounded content with optional real provider headers."""
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):  # noqa: N802
        """Expose fixture readiness and local-only controlled request records."""
        with self.lock:
            result = self.records.copy() if self.path == "/records" else {"ok": True}
        self.respond(200, json.dumps(result).encode())

    def do_POST(self):  # noqa: N802
        """Route main and reviewer independently; main always invokes the real bash tool."""
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        if self.path == "/release":
            with self.lock:
                self.scenarios[body["id"]]["held_release"] = True
            self.respond(200, b'{"ok":true}')
            return
        if self.path == "/control":
            with self.lock:
                self.scenarios[body["id"]] = {**body, "requests": 0}
            self.respond(200, b'{"ok":true}')
            return
        encoded = json.dumps(body, ensure_ascii=False)
        # Most recent user fixture marker wins, including cached Guardian deltas.
        identifiers = re.findall(r"RETRY_CASE_([a-zA-Z0-9_]+)", encoded)
        if not identifiers:
            with self.lock:
                identifiers = [
                    key
                    for key, value in self.scenarios.items()
                    if value.get("source_mode")
                ]
            if len(identifiers) != 1:
                self.respond(400, b'{"error":{"message":"missing fixture marker"}}')
                return
        case_id = identifiers[-1]
        with self.lock:
            case = self.scenarios[case_id]
            is_review = body["model"] == "review"
            action_effect = f"printf '{case_id}" in encoded
            planned_review = is_review and (
                not case.get("source_mode") or action_effect
            )
            if planned_review:
                ordinal = case["requests"]
                case["requests"] += 1
            else:
                ordinal = 0
            plan = case.get("plan", ["allow"])
            selected = (
                plan[min(ordinal, len(plan) - 1)]
                if planned_review
                else "allow"
                if is_review
                else "main"
            )
            row = {
                "case": case_id,
                "review": is_review,
                "ordinal": ordinal,
                "selected": selected,
                "time": time.monotonic(),
                "model": body["model"],
                "session": self.headers.get("X-Agent-Session-Id"),
                "root": self.headers.get("X-Session-Id"),
                "effort": body.get("output_config", {}).get("effort"),
                "failed_history": "FAILED_REVIEW_BRANCH" in encoded,
                "action_effect": action_effect,
                # These are controlled fixture inputs, not production traffic. Keep
                # exact request evidence so Q can inspect full/delta provenance.
                **(
                    {"messages": body.get("messages"), "system": body.get("system")}
                    if is_review or case.get("source_mode")
                    else {}
                ),
            }
            self.records.append(row)
            with self.record.open("a") as stream:
                stream.write(json.dumps(row) + "\n")
        if not is_review and case.get("source_mode"):
            self.respond(
                200,
                frames(source_blocks(body, case, case_id, tool)),
                "text/event-stream",
            )
            return
        if not is_review:
            steps = re.findall(r"EFFECT_STEP_(\d+)", encoded)
            step = steps[-1] if case.get("steps") and steps else None
            call_id = f"effect-{case_id}" + (f"-{step}" if step is not None else "")
            called = any(
                block.get("type") == "tool_use" and block.get("id") == call_id
                for message in body.get("messages", [])
                for block in (
                    message.get("content")
                    if isinstance(message.get("content"), list)
                    else []
                )
            )
            if called:
                response = frames(
                    [
                        {
                            "type": "text",
                            "text": f"FINISHED_RETRY_CASE_{case_id}"
                            + (f"_STEP_{step}" if step is not None else ""),
                        }
                    ]
                )
            else:
                response = frames(
                    [
                        tool(
                            "bash",
                            {
                                "description": "Record isolated review side effect",
                                "command": f"printf '{case_id}\\n' >> retry-effects.txt # RETRY_CASE_{case_id}"
                                + " required-action-evidence"
                                * case.get("action_size", 0),
                            },
                            call_id,
                        )
                    ]
                )
            self.respond(200, response, "text/event-stream")
            return
        if selected == "context":
            self.respond(
                400,
                json.dumps(
                    {
                        "type": "error",
                        "error": {
                            "type": "invalid_request_error",
                            "message": "prompt is too long: 300000 tokens > 258400 maximum",
                        },
                    }
                ).encode(),
                headers={"request-id": f"fixture-{case_id}-{ordinal}"},
            )
            return
        if selected in ("429", "503", "401", "500", "429long", "429stop"):
            status = int(selected[:3])
            self.respond(
                status,
                json.dumps(
                    {
                        "type": "error",
                        "error": {
                            "type": "authentication_error"
                            if status == 401
                            else "overloaded_error",
                            "message": "Controlled fixture failure",
                        },
                    }
                ).encode(),
                headers={
                    "Retry-After": "15"
                    if selected == "429long"
                    else "8"
                    if selected == "429stop"
                    else "1",
                    "request-id": f"fixture-{case_id}-{ordinal}",
                },
            )
            return
        if selected == "timeout":
            time.sleep(95)
            selected = "allow"
        if selected == "transport":
            self.close_connection = True
            return
        if selected == "inspect":
            response = frames(
                [
                    tool(
                        "guardian_read",
                        {"path": "inspection.txt"},
                        f"inspect-{ordinal}",
                    )
                ]
            )
        else:
            text = (
                ""
                if selected == "empty"
                else "invalid fixture verdict"
                if selected == "malformed"
                else (
                    "<block>yes</block><reason>Denied by fixture</reason>"
                    if selected == "deny"
                    else "<block>no</block>"
                )
                if case["policy"] == "nano"
                else json.dumps({"outcome": selected})
            )
            response = frames([{"type": "text", "text": text}])
        self.respond(
            200,
            response,
            "text/event-stream",
            {"request-id": f"fixture-{case_id}-{ordinal}"},
        )

    def log_message(self, *_args):
        """Keep fixture stdout free of requests and prompts."""


def main() -> int:
    """Start an isolated, threaded server and write its dynamically selected port."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    Handler.record = args.record
    Handler.record.touch(exist_ok=False)
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        args.ready_file.write_text(json.dumps({"port": server.server_port}))
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
