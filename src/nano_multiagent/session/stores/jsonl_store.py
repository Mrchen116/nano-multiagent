import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from nano_multiagent.session.serializers import (
    deserialize_entry,
    deserialize_snapshot,
    serialize_entry,
    serialize_snapshot,
)
from nano_multiagent.session.stores.base import LoadedSession, SessionStore


class JsonlSessionStore(SessionStore):
    def __init__(self, *, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def append_event(self, session_id: str, entry: Any) -> None:
        if entry.session_id != session_id:
            raise ValueError("entry.session_id must match append session_id")
        line = json.dumps(serialize_entry(entry), separators=(",", ":"))
        with self._events_path(session_id).open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")

    def load_session(self, session_id: str) -> LoadedSession | None:
        events_path = self._events_path(session_id)
        snapshot_path = self._snapshot_path(session_id)

        events = []
        if events_path.exists():
            with events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    events.append(deserialize_entry(json.loads(line)))

        snapshot: Mapping[str, Any] | None = None
        if snapshot_path.exists():
            with snapshot_path.open("r", encoding="utf-8") as handle:
                snapshot = deserialize_snapshot(json.load(handle))

        if not events and snapshot is None:
            return None
        return LoadedSession(session_id=session_id, events=tuple(events), snapshot=snapshot)

    def save_snapshot(self, session_id: str, snapshot: Mapping[str, Any]) -> None:
        payload = serialize_snapshot(snapshot)
        payload["updated_at"] = datetime.now(UTC).isoformat()
        with self._snapshot_path(session_id).open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))

    def list_session_ids(self, *, limit: int, offset: int) -> tuple[str, ...]:
        event_paths = sorted(
            self._base_dir.glob("*.events.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        session_ids = [path.name.removesuffix(".events.jsonl") for path in event_paths]
        return tuple(session_ids[offset: offset + limit])

    def _events_path(self, session_id: str) -> Path:
        return self._base_dir / f"{session_id}.events.jsonl"

    def _snapshot_path(self, session_id: str) -> Path:
        return self._base_dir / f"{session_id}.snapshot.json"
