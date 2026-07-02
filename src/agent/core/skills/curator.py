"""Deterministic skill lifecycle curator."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from agent.core.utils.fileio import atomic_write

LifecycleAction = Literal["stale", "active", "archive"]

_USAGE_FILENAME = ".usage.json"
_CURATOR_STATE_FILENAME = ".curator_state.json"
_AUTO_SOURCES = {"F3", "F4"}
_SCAN_INTERVAL = timedelta(days=7)
_STALE_AFTER = timedelta(days=30)
_ARCHIVE_AFTER = timedelta(days=90)
_MAX_REVIEWED_SESSION_IDS = 200


@dataclass(frozen=True, slots=True)
class CuratorTransition:
    """Describe one lifecycle transition selected by the Curator."""

    skill_name: str
    action: LifecycleAction
    previous_state: str
    reason: str
    idle_days: int


@dataclass(frozen=True, slots=True)
class CuratorResult:
    """Curator scan result, separate from filesystem mutation."""

    skill_root: Path
    now_iso: str
    transitions: tuple[CuratorTransition, ...]
    skipped: bool = False
    reason: str | None = None


def run_curator_scan(
    *,
    skill_root: Path,
    now_iso: str | None = None,
    force: bool = False,
) -> CuratorResult:
    """Scan one workspace skill root and return deterministic lifecycle transitions."""

    root = skill_root.expanduser().resolve()
    now = _parse_time(now_iso) if now_iso is not None else datetime.now(UTC)
    normalized_now = _format_time(now)
    state = _load_json_object(root / _CURATOR_STATE_FILENAME)
    if not force and not _should_run(state, now=now):
        return CuratorResult(
            skill_root=root,
            now_iso=normalized_now,
            transitions=(),
            skipped=True,
            reason="interval_not_elapsed",
        )

    data = _load_json_object(root / _USAGE_FILENAME)
    transitions: list[CuratorTransition] = []
    for skill_name, raw_record in data.items():
        if not isinstance(skill_name, str) or not isinstance(raw_record, dict):
            continue
        if raw_record.get("source") not in _AUTO_SOURCES:
            continue
        previous_state = str(raw_record.get("state") or "active")
        if previous_state == "archived":
            continue
        last_activity = _last_activity(raw_record)
        if last_activity is None:
            continue
        idle = now - last_activity
        idle_days = max(0, idle.days)
        if idle >= _ARCHIVE_AFTER:
            transitions.append(
                CuratorTransition(
                    skill_name=skill_name,
                    action="archive",
                    previous_state=previous_state,
                    reason="idle_90_days",
                    idle_days=idle_days,
                )
            )
        elif previous_state == "stale" and idle < _STALE_AFTER:
            transitions.append(
                CuratorTransition(
                    skill_name=skill_name,
                    action="active",
                    previous_state=previous_state,
                    reason="recent_activity",
                    idle_days=idle_days,
                )
            )
        elif previous_state == "active" and idle >= _STALE_AFTER:
            transitions.append(
                CuratorTransition(
                    skill_name=skill_name,
                    action="stale",
                    previous_state=previous_state,
                    reason="idle_30_days",
                    idle_days=idle_days,
                )
            )

    return CuratorResult(
        skill_root=root,
        now_iso=normalized_now,
        transitions=tuple(transitions),
    )


def apply_curator_transitions(result: CuratorResult) -> CuratorResult:
    """Apply a previously computed CuratorResult to usage state and skill dirs."""

    if result.skipped:
        return result
    root = result.skill_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    usage_path = root / _USAGE_FILENAME
    data = _load_json_object(usage_path)
    for transition in result.transitions:
        record = data.get(transition.skill_name)
        if not isinstance(record, dict):
            continue
        if transition.action == "stale":
            record["state"] = "stale"
            record["archive_error"] = None
        elif transition.action == "active":
            record["state"] = "active"
            record["archived_at"] = None
            record["archive_error"] = None
        elif transition.action == "archive":
            _archive_skill(
                root=root,
                record=record,
                skill_name=transition.skill_name,
                now_iso=result.now_iso,
            )
    _save_json_object(usage_path, data)
    _write_curator_state(
        root / _CURATOR_STATE_FILENAME,
        now_iso=result.now_iso,
        transition_count=len(result.transitions),
    )
    return result


def mark_reviewed_session_ids(
    *, curator_state_path: Path, session_ids: list[str] | tuple[str, ...]
) -> None:
    """Append reviewed session ids to Curator state with a bounded cap."""

    state_path = curator_state_path.expanduser().resolve()
    state = _load_json_object(state_path)
    existing = [item for item in state.get("reviewed_session_ids", []) if isinstance(item, str)]
    seen = set(existing)
    for session_id in session_ids:
        if session_id in seen:
            continue
        seen.add(session_id)
        existing.append(session_id)
    state["reviewed_session_ids"] = existing[-_MAX_REVIEWED_SESSION_IDS:]
    _save_json_object(state_path, state)


def reviewed_session_ids(*, curator_state_path: Path) -> frozenset[str]:
    """Return reviewed session ids stored by prior skill batch reviews."""

    state = _load_json_object(curator_state_path.expanduser().resolve())
    return frozenset(
        item for item in state.get("reviewed_session_ids", []) if isinstance(item, str)
    )


def _archive_skill(
    *,
    root: Path,
    record: dict[str, Any],
    skill_name: str,
    now_iso: str,
) -> None:
    source = root / skill_name
    destination = root / ".archive" / skill_name
    if not source.exists():
        record["state"] = "archived"
        record["archived_at"] = now_iso
        record["archive_error"] = None
        return
    if destination.exists():
        record["archive_error"] = f"archive destination already exists: {destination}"
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(source), str(destination))
    except OSError as exc:
        record["archive_error"] = str(exc)
        return
    record["state"] = "archived"
    record["archived_at"] = now_iso
    record["archive_error"] = None


def _write_curator_state(
    state_path: Path, *, now_iso: str, transition_count: int
) -> None:
    state = _load_json_object(state_path)
    state["last_run_at"] = now_iso
    state["run_count"] = int(state.get("run_count") or 0) + 1
    state["last_run_summary"] = f"applied {transition_count} transition(s)"
    state.setdefault("reviewed_session_ids", [])
    _save_json_object(state_path, state)


def _should_run(state: dict[str, Any], *, now: datetime) -> bool:
    last_run_at = state.get("last_run_at")
    if not isinstance(last_run_at, str) or not last_run_at.strip():
        return True
    return now - _parse_time(last_run_at) >= _SCAN_INTERVAL


def _last_activity(record: dict[str, Any]) -> datetime | None:
    candidates: list[datetime] = []
    for key in ("last_used_at", "created_at"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(_parse_time(value))
    if not candidates:
        return None
    return max(candidates)


def _parse_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return loaded


def _save_json_object(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(
        path,
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


__all__ = [
    "CuratorResult",
    "CuratorTransition",
    "apply_curator_transitions",
    "mark_reviewed_session_ids",
    "reviewed_session_ids",
    "run_curator_scan",
]
