"""Persistent launch consent identities for Workflow."""

from __future__ import annotations

import json
import threading
from pathlib import Path


class WorkflowConsentStore:
    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()
        self._lock = threading.Lock()

    def contains(self, identity: str) -> bool:
        with self._lock:
            return identity in self._read()

    def add(self, identity: str) -> None:
        with self._lock:
            values = self._read()
            values.add(identity)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp = self._path.with_suffix(".json.tmp")
            temp.write_text(
                json.dumps(sorted(values), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temp.replace(self._path)

    def _read(self) -> set[str]:
        if not self._path.is_file():
            return set()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        if not isinstance(raw, list):
            return set()
        return {item for item in raw if isinstance(item, str) and item}
