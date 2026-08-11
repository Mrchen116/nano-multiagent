#!/usr/bin/env python3
"""Run the production Gateway with one controlled self-evolution stream fault."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from personal_assistant.gateway import background_subscriptions


def _required_path(name: str) -> Path:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return Path(value)


_STATE_PATH = _required_path("NANO_E2E_REPLAY_FAULT_STATE")
_ARM_PATH = _required_path("NANO_E2E_REPLAY_FAULT_ARM")
_STATE_PATH.write_text("", encoding="utf-8")
_fault_sequence: int | None = None
_replayed = False


def _record(kind: str, *, session_id: str, sequence: int | None = None) -> None:
    payload: dict[str, Any] = {"kind": kind, "session_id": session_id}
    if sequence is not None:
        payload["sequence"] = sequence
    with _STATE_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, separators=(",", ":")) + "\n")


_original_stream_session = background_subscriptions._KernelStreamAdapter.stream_session


async def _stream_with_one_replay_fault(
    self: Any,
    *,
    session_id: str,
    last_event_id: int | None = None,
    workspace_root: str | None = None,
    **kwargs: object,
):
    """End one armed stream before delivery, then expose the replayed event."""

    global _fault_sequence, _replayed
    _record("stream_opened", session_id=session_id)
    async for event in _original_stream_session(
        self,
        session_id=session_id,
        last_event_id=last_event_id,
        workspace_root=workspace_root,
        **kwargs,
    ):
        sequence = event.get("_id") or event.get("sequence_num")
        marked_skill = (
            event.get("event") == "skill_created"
            and event.get("source") == "self_evolution"
            and isinstance(sequence, int)
        )
        if marked_skill and _ARM_PATH.exists() and _fault_sequence is None:
            _fault_sequence = sequence
            _ARM_PATH.unlink()
            _record("disconnected", session_id=session_id, sequence=sequence)
            raise ConnectionError("controlled self-evolution stream disconnect")
        if marked_skill and sequence == _fault_sequence and not _replayed:
            _replayed = True
            _record("replayed", session_id=session_id, sequence=sequence)
        yield event


background_subscriptions._KernelStreamAdapter.stream_session = (  # noqa: SLF001
    _stream_with_one_replay_fault
)

from personal_assistant.main import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
