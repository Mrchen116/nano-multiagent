#!/usr/bin/env python3
"""Deterministic provider for real bash jobs, stop, Schedule and heartbeat E2E."""

from __future__ import annotations

import http.server
import json
import os
import re
import sys
import threading

from anthropic_sse_compaction_recording import (
    _frames_bytes,
    _message_start,
    _message_end,
    _sse_text,
)


def _tool(call_id: str, name: str, arguments: dict) -> bytes:
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
                        "id": call_id,
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
                        "partial_json": json.dumps(arguments),
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


def _text(message: dict) -> str:
    content = message.get("content", [])
    if isinstance(content, str):
        return content
    return "\n".join(
        block.get("text", "") for block in content if block.get("type") == "text"
    )


def _results(body: dict) -> dict[str, dict]:
    return {
        block["tool_use_id"]: block
        for message in body.get("messages", [])
        if isinstance(message.get("content"), list)
        for block in message["content"]
        if block.get("type") == "tool_result"
    }


def _response(body: dict, scenario: str) -> bytes:
    if any(tool["name"].startswith("guardian_") for tool in body.get("tools", [])):
        return _sse_text('{"outcome":"allow"}', input_tokens=100)
    if not body.get("tools"):
        return _sse_text("<block>no</block>", input_tokens=100)
    messages = body["messages"]
    user_texts = [
        _text(message)
        for message in messages
        if message["role"] == "user"
        and _text(message)
        and not _text(message).startswith("Current runtime context.")
    ]
    latest = user_texts[-1]
    results = _results(body)
    if "EVENTS-AFTER-STOP" in latest:
        return _sse_text("STOP-RECOVERED", input_tokens=100)
    if scenario in {"bash", "stop"}:
        if "event-delivery" in results:
            if results["event-delivery"].get("is_error"):
                raise ValueError(f"send_message failed: {results['event-delivery']}")
            return _sse_text("Job result delivered.", input_tokens=100)
        if "event-output" in results:
            result = results["event-output"]
            if result.get("is_error"):
                raise ValueError(f"job_output failed: {result}")
            return _tool(
                "event-delivery",
                "send_message",
                {
                    "target": "current",
                    "text": "JOB-FINISHED " + json.dumps(result["content"]),
                },
            )
        if "event-bash" not in results:
            command = next(
                re.search(r"EVENTS-COMMAND (\{[^\n]+\})", text)
                for text in user_texts
                if "EVENTS-COMMAND " in text
            )
            return _tool("event-bash", "bash", json.loads(command.group(1)))
        result = results["event-bash"]
        if result.get("is_error"):
            raise ValueError(f"bash failed: {result}")
        result_text = json.dumps(result["content"])
        job = re.search(r"background job ([a-zA-Z0-9_-]+)", result_text)
        if job and job.group(1) in latest and "completed" in latest:
            return _tool("event-output", "job_output", {"job_id": job.group(1)})
        return _sse_text("JOB-LAUNCHED", input_tokens=100)
    if scenario == "cron":
        if "EVENTS-SCHEDULE-FIRED" in latest and "EVENTS-REGISTER" not in latest:
            return _sse_text("SCHEDULE-DELIVERED", input_tokens=100)
        if "event-schedule" not in results:
            return _tool(
                "event-schedule",
                "schedule_create",
                {
                    "title": "Deterministic one-shot",
                    "prompt": "EVENTS-SCHEDULE-FIRED",
                    "after_seconds": 2,
                },
            )
        if results["event-schedule"].get("is_error"):
            raise ValueError(f"schedule_create failed: {results['event-schedule']}")
        return _sse_text("SCHEDULE-REGISTERED", input_tokens=100)
    if scenario == "heartbeat":
        text = "HEARTBEAT-DELIVERED" if "EVENTS-HEARTBEAT-FIRED" in latest else "READY"
        return _sse_text(text, input_tokens=100)
    raise ValueError(f"unknown scenario: {scenario}")


class Handler(http.server.BaseHTTPRequestHandler):
    lock = threading.Lock()
    record_path = os.environ["NANO_FIXTURE_RECORD_PATH"]
    scenario = os.environ["NANO_FIXTURE_SCENARIO"]

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with self.lock, open(self.record_path, "a", encoding="utf-8") as output:
            output.write(json.dumps(body, ensure_ascii=False) + "\n")
        try:
            response = _response(body, self.scenario)
        except (ValueError, KeyError, StopIteration) as error:
            self.send_error(422, str(error))
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(response)
        self.wfile.flush()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


if __name__ == "__main__":
    open(Handler.record_path, "w").close()
    http.server.ThreadingHTTPServer(
        ("127.0.0.1", int(sys.argv[1])), Handler
    ).serve_forever()
