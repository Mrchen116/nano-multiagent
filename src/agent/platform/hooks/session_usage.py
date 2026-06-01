"""Per-hook-registry session usage snapshot contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent.core.hooks.registry import HookRegistry

SESSION_USAGE_SNAPSHOT_READER_STATE_KEY = "session_usage_snapshot_reader"


@dataclass(frozen=True, slots=True)
class SessionUsageSnapshot:
    """Exact session usage counters aggregated from provider usage payloads."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    last_prompt_tokens: int
    last_completion_tokens: int
    last_total_tokens: int
    turn_count: int


SessionUsageSnapshotReader = Callable[[str], SessionUsageSnapshot | None]


def set_session_usage_snapshot_reader(
    *,
    registry: HookRegistry,
    reader: SessionUsageSnapshotReader | None,
) -> None:
    """Register or clear usage snapshot reader on one hook registry."""

    registry.set_extension_state(SESSION_USAGE_SNAPSHOT_READER_STATE_KEY, reader)


def get_session_usage_snapshot(
    *, registry: HookRegistry, session_id: str
) -> SessionUsageSnapshot | None:
    """Resolve usage snapshot for a session from one hook registry."""

    reader = registry.get_extension_state(SESSION_USAGE_SNAPSHOT_READER_STATE_KEY)
    if not callable(reader):
        return None
    snapshot = reader(session_id)
    if not isinstance(snapshot, SessionUsageSnapshot):
        return None
    return snapshot
