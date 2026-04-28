"""Non-interactive `--text` runner: NDJSON output until run terminal."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, TextIO

from coding_cli.client import ServerClient


def _is_terminal_run_status(event: dict[str, Any]) -> bool:
    if event.get("event") != "run_status":
        return False
    status = event.get("status")
    return status in {"completed", "failed", "cancelled"}


async def run_text(
    client: ServerClient,
    *,
    session_id: str,
    text: str,
    out: TextIO = sys.stdout,
) -> int:
    """Open stream, submit message, filter by run_id, output NDJSON until terminal.

    Returns:
        0 if run completed, 1 if run failed/cancelled, 2 for stream-level error.
    """
    submit = client.submit_message(session_id=session_id, text=text)
    out.write(json.dumps({"event": "submit_response", **submit}, ensure_ascii=False) + "\n")
    out.flush()

    target_run_id = submit["run_id"]
    anchor_sequence = submit.get("anchor_sequence")

    async for event in client.stream_session(
        session_id=session_id,
        last_event_id=anchor_sequence,
    ):
        if event.get("run_id") != target_run_id:
            continue
        out.write(json.dumps(event, ensure_ascii=False) + "\n")
        out.flush()
        if _is_terminal_run_status(event):
            return 0 if event["status"] == "completed" else 1
        if event.get("event") == "error":
            return 2

    return 1
