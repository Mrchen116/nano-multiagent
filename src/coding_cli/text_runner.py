"""Non-interactive ``--text`` runner: NDJSON output until run terminal.

Accepts any Kernel-compatible object with ``submit(...)`` and
``stream(session_id)`` methods.  No HTTP dependency.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from agent.sdk import TERMINAL_RUN_STATUSES as _TERMINAL_STATUSES


async def run_text(
    kernel: Any,
    *,
    session_id: str,
    text: str,
    out: TextIO = sys.stdout,
    workspace_root: Path | None = None,
) -> int:
    """Submit text to kernel stream, output NDJSON until terminal run status.

    Args:
        kernel: Kernel-compatible object with submit() and stream() methods.
        session_id: Session to submit to.
        text: User text to submit.
        out: Output stream (NDJSON lines).
        workspace_root: Workspace root for session storage.

    Returns:
        0 if run completed, 1 if run failed/cancelled.
    """
    from pathlib import Path as _Path

    resolved_root = workspace_root or _Path.cwd()
    run_record = kernel.submit(
        session_id=session_id,
        parts=[{"type": "text", "text": text}],
        workspace_root=resolved_root,
    )
    run_id = run_record.run_id

    out.write(
        json.dumps({"event": "submit_response", "run_id": run_id}, ensure_ascii=False)
        + "\n"
    )
    _flush(out)

    final_status = "failed"
    async for event in kernel.stream(session_id):
        event_run_id = event.get("run_id")
        if event_run_id is not None and event_run_id != run_id:
            continue
        out.write(json.dumps(event, ensure_ascii=False) + "\n")
        _flush(out)
        if event.get("event") == "run_status":
            status = event.get("status", "")
            if status in _TERMINAL_STATUSES:
                final_status = status
                break

    return 0 if final_status == "completed" else 1


def _flush(out: TextIO) -> None:
    flush_fn = getattr(out, "flush", None)
    if callable(flush_fn):
        flush_fn()
