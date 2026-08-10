"""File-backed test doubles shared by session continuity recovery subprocesses."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from personal_assistant.channels.base import OutboundMessage


class Kernel:
    """Create deterministic process-local Kernel session identities."""

    def __init__(self, *, prefix: str) -> None:
        self._prefix = prefix
        self._created = 0

    async def create_session(self, **_kwargs: Any) -> SimpleNamespace:
        self._created += 1
        return SimpleNamespace(session_id=f"{self._prefix}-{self._created}")


class FileChannel:
    """Persist external control deliveries in the process-shared ledger."""

    name = "feishu:agent-a"

    def __init__(self, runtime: Path) -> None:
        self._runtime = runtime

    def start(self, _on_inbound: object) -> None:
        return None

    def send(self, outbound: OutboundMessage) -> None:
        append_ledger(
            self._runtime,
            {
                "type": "control_confirmation",
                "target_chat_id": outbound.target_chat_id,
                "text": outbound.text,
            },
        )

    def stop(self) -> None:
        return None


class FileBoundaryConnection:
    """Acknowledge boundary delivery while recording the visible payload."""

    def __init__(self, runtime: Path) -> None:
        self._runtime = runtime

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, object]
    ) -> dict[str, object]:
        assert message_type == "agent.config.boundary"
        append_ledger(
            self._runtime,
            {
                "type": "boundary_applied",
                "boundary_id": payload["boundary_id"],
                "conversation_id": payload["conversation_id"],
            },
        )
        return {"boundary_id": payload["boundary_id"]}


def read_state(runtime: Path) -> dict[str, object]:
    """Read the latest process-shared barrier state."""

    path = runtime / "barrier-state.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_state(runtime: Path, state: dict[str, object]) -> None:
    """Replace the process-shared barrier state atomically enough for the test."""

    (runtime / "barrier-state.json").write_text(json.dumps(state), encoding="utf-8")


def append_ledger(runtime: Path, event: dict[str, object]) -> None:
    """Append one externally visible delivery to the shared recovery ledger."""

    with (runtime / "fake-external-chat.jsonl").open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(event, ensure_ascii=False) + "\n")
