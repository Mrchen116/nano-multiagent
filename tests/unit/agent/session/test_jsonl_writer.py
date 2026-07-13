"""Deterministic lifecycle tests for the shared JSONL writer."""

from __future__ import annotations

import json
from pathlib import Path

from agent.core.session.jsonl_writer import JsonlWriter


def test_close_flushes_pending_entries_and_stops_thread(tmp_path: Path) -> None:
    writer = JsonlWriter()
    path = tmp_path / "session.jsonl"
    writer.enqueue_raw(path, {"type": "turn", "uuid": "msg_pending"})

    writer.close()

    assert not writer._thread.is_alive()
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "type": "turn",
        "uuid": "msg_pending",
    }
    writer.close()
