"""Skill usage sidecar persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Sequence

from agent.core.utils.fileio import atomic_write

SkillSource = Literal["F1", "F2", "F3", "F4", "unknown"]

_USAGE_FILENAME = ".usage.json"
_MAX_SESSION_REFS = 60
_MAX_RECENT_CALL_KEYS = 200
_VALID_SOURCES = {"F1", "F2", "F3", "F4", "unknown"}
_AUTO_SOURCES = {"F3", "F4"}
_DEFAULT_F4_THRESHOLD = 20


@dataclass(frozen=True, slots=True)
class F4Trigger:
    """Pure data returned when a skill crosses the per-skill batch threshold."""

    skill_name: str
    skill_root: Path
    session_refs: tuple[dict[str, Any], ...]
    call_key: str


@dataclass(frozen=True, slots=True)
class UsageBumpResult:
    """Result of a usage bump."""

    counted: bool
    usage_path: Path
    trigger: F4Trigger | None = None


@dataclass(frozen=True, slots=True)
class SkillSessionRef:
    """A skill invocation reference used for compaction reinjection."""

    name: str
    location: Path
    root_id: str


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
    location: Path | str | None = None,
    now_iso: str | None = None,
    threshold: int = _DEFAULT_F4_THRESHOLD,
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
    ref: dict[str, Any] = {
        "session_id": session_id,
        "tool_call_id": tool_call_id,
        "timestamp": now,
    }
    if location is not None:
        ref["location"] = str(Path(location).expanduser().resolve())
    refs.append(ref)
    record["session_refs"] = refs[-_MAX_SESSION_REFS:]
    recent_keys.append(call_key)
    record["recent_call_keys"] = recent_keys[-_MAX_RECENT_CALL_KEYS:]
    record["uses_since_last_B"] = int(record.get("uses_since_last_B") or 0) + 1
    record.setdefault("source", _normalize_source(source))
    record.setdefault("created_at", now)
    record.setdefault("state", "active")
    trigger = _maybe_build_f4_trigger(
        record=record,
        skill_name=skill_name,
        skill_root=root,
        call_key=call_key,
        threshold=threshold,
    )
    _save_usage(root, data)
    return UsageBumpResult(
        counted=True,
        usage_path=root / _USAGE_FILENAME,
        trigger=trigger,
    )


def reset_uses_since_last_batch(*, skill_root: Path, skill_name: str) -> None:
    """Reset F4 usage counter after a batch review has been accepted for enqueue."""

    root = skill_root.expanduser().resolve()
    data = _load_usage(root)
    record = data.get(skill_name)
    if not isinstance(record, dict):
        return
    record["uses_since_last_B"] = 0
    _save_usage(root, data)


def source_from_metadata(metadata: dict[str, Any] | Any) -> SkillSource:
    """Return controlled skill source from session metadata."""
    raw = metadata.get("skill_creation_source") if isinstance(metadata, dict) else None
    return _normalize_source(raw or "F1")


def skill_refs_for_session(
    *, skill_roots: Sequence[Path], session_id: str
) -> tuple[SkillSessionRef, ...]:
    """Return skill usage refs for a session across usage sidecars."""

    refs: list[SkillSessionRef] = []
    seen: set[tuple[str, str]] = set()
    for root in _dedupe_roots(skill_roots):
        data = _load_usage(root)
        for skill_name, record in data.items():
            if not isinstance(skill_name, str) or not isinstance(record, dict):
                continue
            for ref in _list_of_mappings(record.get("session_refs")):
                if ref.get("session_id") != session_id:
                    continue
                raw_location = ref.get("location")
                location = (
                    Path(raw_location).expanduser().resolve()
                    if isinstance(raw_location, str) and raw_location
                    else (root / skill_name / "SKILL.md").expanduser().resolve()
                )
                key = (skill_name, str(location))
                if key in seen:
                    continue
                seen.add(key)
                refs.append(
                    SkillSessionRef(
                        name=skill_name,
                        location=location,
                        root_id=str(root.expanduser().resolve()),
                    )
                )
    return tuple(refs)


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


def _maybe_build_f4_trigger(
    *,
    record: dict[str, Any],
    skill_name: str,
    skill_root: Path,
    call_key: str,
    threshold: int,
) -> F4Trigger | None:
    if threshold <= 0:
        return None
    if record.get("source") not in _AUTO_SOURCES:
        return None
    if int(record.get("uses_since_last_B") or 0) < threshold:
        return None
    return F4Trigger(
        skill_name=skill_name,
        skill_root=skill_root,
        session_refs=tuple(_list_of_mappings(record.get("session_refs"))),
        call_key=call_key,
    )


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


def _dedupe_roots(roots: Sequence[Path]) -> tuple[Path, ...]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = root.expanduser().resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resolved)
    return tuple(deduped)


__all__ = [
    "SkillSource",
    "F4Trigger",
    "SkillSessionRef",
    "UsageBumpResult",
    "bump_skill_usage",
    "ensure_skill_record",
    "reset_uses_since_last_batch",
    "skill_refs_for_session",
    "source_from_metadata",
    "utc_now_iso",
]
