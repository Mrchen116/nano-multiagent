"""Skill usage sidecar persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from agent.core.utils.fileio import atomic_write

SkillSource = Literal["F1", "F2", "F3", "F4", "unknown"]

_USAGE_FILENAME = ".usage.json"
_MAX_SESSION_REFS = 60
_MAX_RECENT_CALL_KEYS = 200
_VALID_SOURCES = {"F1", "F2", "F3", "F4", "unknown"}


@dataclass(frozen=True, slots=True)
class UsageBumpResult:
    """Result of a usage bump."""

    counted: bool
    usage_path: Path


def utc_now_iso() -> str:
    """Return current UTC timestamp for usage records."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_skill_record(
    *,
    skill_root: Path,
    skill_name: str,
    source: str,
    now_iso: str | None = None,
) -> None:
    """Ensure a skill has a usage record without incrementing use counters."""
    root = skill_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    now = now_iso or utc_now_iso()
    data = _load_usage(root)
    record = data.get(skill_name)
    if not isinstance(record, dict):
        data[skill_name] = _new_record(source=_normalize_source(source), now_iso=now)
    else:
        record.setdefault("source", _normalize_source(source))
        record.setdefault("state", "active")
        record.setdefault("created_at", now)
        record.setdefault("use_count", 0)
        record.setdefault("last_used_at", None)
        record.setdefault("session_refs", [])
        record.setdefault("recent_call_keys", [])
        record.setdefault("uses_since_last_B", 0)
    _save_usage(root, data)


def bump_skill_usage(
    *,
    skill_root: Path,
    skill_name: str,
    session_id: str | None,
    tool_call_id: str | None,
    source: str,
    now_iso: str | None = None,
) -> UsageBumpResult:
    """Increment usage for a successful skill_view call.

    Duplicate ``session_id:tool_call_id`` pairs are treated as replay and do not
    increment counters or append session refs.
    """
    root = skill_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    now = now_iso or utc_now_iso()
    data = _load_usage(root)
    record = data.get(skill_name)
    if not isinstance(record, dict):
        record = _new_record(source=_normalize_source(source), now_iso=now)
        data[skill_name] = record

    call_key = _call_key(session_id=session_id, tool_call_id=tool_call_id, now_iso=now)
    recent_keys = _list_of_strings(record.get("recent_call_keys"))
    if call_key in recent_keys:
        _save_usage(root, data)
        return UsageBumpResult(counted=False, usage_path=root / _USAGE_FILENAME)

    record["use_count"] = int(record.get("use_count") or 0) + 1
    record["last_used_at"] = now
    if record.get("state") == "stale":
        record["state"] = "active"
    refs = _list_of_mappings(record.get("session_refs"))
    refs.append(
        {"session_id": session_id, "tool_call_id": tool_call_id, "timestamp": now}
    )
    record["session_refs"] = refs[-_MAX_SESSION_REFS:]
    recent_keys.append(call_key)
    record["recent_call_keys"] = recent_keys[-_MAX_RECENT_CALL_KEYS:]
    record["uses_since_last_B"] = int(record.get("uses_since_last_B") or 0) + 1
    record.setdefault("source", _normalize_source(source))
    record.setdefault("created_at", now)
    record.setdefault("state", "active")
    _save_usage(root, data)
    return UsageBumpResult(counted=True, usage_path=root / _USAGE_FILENAME)


def source_from_metadata(metadata: dict[str, Any] | Any) -> SkillSource:
    """Return controlled skill source from session metadata."""
    raw = metadata.get("skill_creation_source") if isinstance(metadata, dict) else None
    return _normalize_source(raw or "F1")


def _new_record(*, source: SkillSource, now_iso: str) -> dict[str, Any]:
    return {
        "use_count": 0,
        "last_used_at": None,
        "session_refs": [],
        "recent_call_keys": [],
        "uses_since_last_B": 0,
        "source": source,
        "state": "active",
        "created_at": now_iso,
        "archived_at": None,
    }


def _load_usage(skill_root: Path) -> dict[str, Any]:
    path = skill_root / _USAGE_FILENAME
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return loaded


def _save_usage(skill_root: Path, data: dict[str, Any]) -> None:
    skill_root.mkdir(parents=True, exist_ok=True)
    atomic_write(
        skill_root / _USAGE_FILENAME,
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _normalize_source(source: str | None) -> SkillSource:
    value = source if isinstance(source, str) else "unknown"
    if value not in _VALID_SOURCES:
        return "unknown"
    return value  # type: ignore[return-value]


def _call_key(
    *, session_id: str | None, tool_call_id: str | None, now_iso: str
) -> str:
    if session_id and tool_call_id:
        return f"{session_id}:{tool_call_id}"
    if tool_call_id:
        return f"unknown-session:{tool_call_id}"
    return f"ephemeral:{now_iso}:{id(now_iso)}"


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


__all__ = [
    "SkillSource",
    "UsageBumpResult",
    "bump_skill_usage",
    "ensure_skill_record",
    "source_from_metadata",
    "utc_now_iso",
]
