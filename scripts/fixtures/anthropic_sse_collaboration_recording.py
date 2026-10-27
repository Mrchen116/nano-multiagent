#!/usr/bin/env python3
"""Deterministic native child and cross-chat tool responses; never contacts a model."""

from __future__ import annotations

import http.server
import json
import os
import re
import sys
import threading

from anthropic_sse_tool_approval_recording import (
    _frames_bytes,
    _message_end,
    _message_start,
    _sse_text,
)


def _tool(call_id: str, name: str, arguments: dict) -> bytes:
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


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(
        block.get("text", "") for block in content if isinstance(block, dict)
    )


def _user_texts(body: dict) -> list[str]:
    return [
        _text(message["content"])
        for message in body["messages"]
        if message["role"] == "user"
    ]


def _results(body: dict) -> dict[str, dict]:
    return {
        block["tool_use_id"]: block
        for message in body["messages"]
        if isinstance(message["content"], list)
        for block in message["content"]
        if block.get("type") == "tool_result"
    }


def _json_result(results: dict, call: str) -> dict:
    result = results[call]
    if result.get("is_error"):
        raise ValueError(f"{call} failed: {result}")
    return json.loads(_text(result["content"]))


def _foreground(body: dict) -> bytes:
    texts = _user_texts(body)
    current = next(
        (
            text
            for text in reversed(texts)
            if re.search(r"FOREGROUND_|CHILD_SUCCESS|CHILD_FAILURE|AFTER_FAILURE", text)
        ),
        "",
    )
    if "CHILD_SUCCESS" in current:
        return _sse_text("CHILD-OUTPUT")
    if "CHILD_FAILURE" in current:
        raise RuntimeError("CONTROLLED_CHILD_FAILURE")
    if "AFTER_FAILURE" in current:
        return _sse_text("STILL-RESPONSIVE")
    results = _results(body)
    failure = "FOREGROUND_FAILURE" in current
    call = "spawn-failure" if failure else "spawn-success"
    if call not in results:
        return _tool(
            call,
            "subagent",
            {
                "prompt": "CHILD_FAILURE" if failure else "CHILD_SUCCESS",
                "description": "Controlled child failure"
                if failure
                else "Child output",
                "run_in_background": False,
            },
        )
    return _sse_text("FAILURE-OBSERVED" if failure else "CHILD-OUTPUT-RECEIVED")


def _global(body: dict) -> bytes:
    texts = _user_texts(body)
    joined = "\n".join(texts)
    results = _results(body)
    if "J2_CHILD_INITIAL" in joined:
        if "J2_CHILD_REVISION " not in joined:
            return _sse_text("Waiting for the parent's revision.")
        if "child-report" in results:
            return _sse_text("Revision sent to parent.")
        parent = re.search(r"Agent ([^\s]+) sent a message: J2_CHILD_REVISION", joined)
        revision = re.search(r"J2_CHILD_REVISION (AMEND[A-Z0-9]+)", joined)
        if not parent or not revision:
            raise ValueError("child request lost parent identity or revision")
        return _tool(
            "child-report",
            "send_message",
            {
                "agent_id": parent[1],
                "message": "CHILD-REVISED " + revision[1],
            },
        )
    if "check-a" not in results:
        return _tool("check-a", "inbox", {"action": "check"})
    if "read-a" not in results:
        source = _json_result(results, "check-a")["sources"][0]["target"]
        return _tool("read-a", "inbox", {"action": "read", "target": source})
    original = _json_result(results, "read-a")
    if "J2_START" not in json.dumps(original):
        raise ValueError("main request lost original Inbox body")
    if "spawn-global" not in results:
        return _tool(
            "spawn-global",
            "subagent",
            {
                "prompt": "J2_CHILD_INITIAL",
                "description": "Await same-child revision",
                "run_in_background": True,
            },
        )
    if joined.count("New messages are waiting in your Inbox.") < 2:
        return _sse_text("Child started; waiting for the revision.")
    if "check-b" not in results:
        return _tool("check-b", "inbox", {"action": "check"})
    if "read-b" not in results:
        source = _json_result(results, "check-b")["sources"][0]["target"]
        return _tool("read-b", "inbox", {"action": "read", "target": source})
    amended = _json_result(results, "read-b")
    revision = re.search(r"AMEND[A-Z0-9]+", json.dumps(amended))
    if not revision:
        raise ValueError("main request lost amended Inbox body")
    if "follow-child" not in results:
        child = re.search(
            r"started subagent ([^\s]+)", _text(results["spawn-global"]["content"])
        )
        if not child:
            raise ValueError("subagent result did not expose its real child ID")
        return _tool(
            "follow-child",
            "send_message",
            {
                "agent_id": child[1],
                "message": "J2_CHILD_REVISION " + revision[0],
            },
        )
    if "CHILD-REVISED " + revision[0] not in joined:
        return _sse_text("Revision accepted by child; waiting for its result.")
    if "deliver" not in results:
        target = _json_result(results, "check-a")["sources"][0]["target"]
        return _tool(
            "deliver",
            "send_message",
            {
                "target": target,
                "text": "CHILD-REVISED " + revision[0],
            },
        )
    return _sse_text("Revised child result delivered once to the original chat.")


class Handler(http.server.BaseHTTPRequestHandler):
    record_path = ""
    mode = ""
    lock = threading.Lock()

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        row = {
            "request": body,
            "session": self.headers.get("X-Agent-Session-Id"),
            "root": self.headers.get("X-Session-Id"),
        }
        with self.lock:
            with open(self.record_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        try:
            if not body.get("tools"):
                response = _sse_text("<block>no</block>")
            else:
                response = _global(body) if self.mode == "global" else _foreground(body)
        except (ValueError, RuntimeError, KeyError, IndexError) as error:
            payload = json.dumps(
                {
                    "type": "error",
                    "error": {"type": "invalid_request_error", "message": str(error)},
                }
            ).encode()
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(response)
        self.wfile.flush()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


if __name__ == "__main__":
    Handler.record_path = os.environ["NANO_FIXTURE_RECORD_PATH"]
    Handler.mode = os.environ.get("NANO_FIXTURE_COLLABORATION", "foreground")
    with open(Handler.record_path, "w", encoding="utf-8"):
        pass
    http.server.ThreadingHTTPServer(
        ("127.0.0.1", int(sys.argv[1])), Handler
    ).serve_forever()
