#!/usr/bin/env python3
"""Deterministic A -> B mention responses; routing remains entirely in the product."""

from __future__ import annotations

import http.server
import json
import os
import re
import sys

from anthropic_sse_compaction_recording import _sse_text


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with open(os.environ["NANO_FIXTURE_RECORD_PATH"], "a") as output:
            output.write(json.dumps(body, ensure_ascii=False) + "\n")
        system = json.dumps(body.get("system"), ensure_ascii=False)
        messages = json.dumps(body.get("messages"), ensure_ascii=False)
        if "FIXTURE_GROUP_B" in system:
            reply = "GROUP_B_RECEIVED"
        elif "FIXTURE_GROUP_A" in system:
            if "GROUP_SOLO" in messages:
                reply = "GROUP_A_ONLY"
            else:
                target = re.search(r"FIXTURE_GROUP_A target=([\w-]+)", system)
                if not target:
                    self.send_error(422, "missing group B user identity")
                    return
                reply = f'<mention type="user" target_id="{target[1]}"/> GROUP_RELAY'
        else:
            self.send_error(422, "unexpected request outside group fixture")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(_sse_text(reply, input_tokens=100))

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


if __name__ == "__main__":
    http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
