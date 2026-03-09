"""Compaction planner that selects safe history cut points."""

from typing import Mapping, Sequence

from nano_multiagent.core.session.entries import CompactionEntry, SessionEntry, SessionEntryKind

from .types import CompactionPlan, CompactionReason


class CompactionPlanner:
    """Plan compaction ranges while preserving critical tool-call/result integrity."""

    def __init__(self, *, min_kept_messages: int = 8) -> None:
        self._min_kept_messages = max(min_kept_messages, 1)

    def plan(
        self,
        *,
        events: Sequence[SessionEntry | CompactionEntry],
        reason: CompactionReason,
    ) -> CompactionPlan | None:
        """Build compaction plan for turn-appended events.

        Args:
            events: Session entries in chronological order.
            reason: Compaction trigger reason.

        Returns:
            A compaction plan when eligible, otherwise `None`.
        """

        turn_events = tuple(
            event for event in events
            if isinstance(event, SessionEntry) and event.kind is SessionEntryKind.TURN_APPENDED
        )
        if len(turn_events) <= self._min_kept_messages:
            return None

        keep_start = len(turn_events) - self._min_kept_messages
        # Boundary invariant: compaction cut must not split one tool call/result
        # pair across dropped and kept slices, otherwise replay context becomes
        # semantically inconsistent for subsequent model turns.
        while keep_start > 0 and _splits_tool_pair(turn_events, keep_start):
            keep_start -= 1

        if keep_start <= 0:
            return None

        dropped_events = turn_events[:keep_start]
        kept_events = turn_events[keep_start:]
        return CompactionPlan(
            reason=reason,
            first_kept_event_id=kept_events[0].entry_id,
            dropped_events=dropped_events,
            kept_events=kept_events,
        )


def _splits_tool_pair(events: Sequence[SessionEntry], keep_start: int) -> bool:
    dropped_call_ids: set[str] = set()
    dropped_result_ids: set[str] = set()
    for event in events[:keep_start]:
        phase, call_id = _tool_marker(event)
        if call_id is None:
            continue
        if phase == "call":
            dropped_call_ids.add(call_id)
        if phase == "result":
            dropped_result_ids.add(call_id)

    kept_call_ids: set[str] = set()
    kept_result_ids: set[str] = set()
    for event in events[keep_start:]:
        phase, call_id = _tool_marker(event)
        if call_id is None:
            continue
        if phase == "call":
            kept_call_ids.add(call_id)
        if phase == "result":
            kept_result_ids.add(call_id)

    return bool((dropped_call_ids & kept_result_ids) or (dropped_result_ids & kept_call_ids))


def _tool_marker(entry: SessionEntry) -> tuple[str | None, str | None]:
    metadata = entry.data.get("metadata")
    if not isinstance(metadata, Mapping):
        return None, None
    phase = metadata.get("tool_phase")
    call_id = metadata.get("tool_call_id")
    if not isinstance(phase, str) or not isinstance(call_id, str):
        return None, None
    return phase, call_id
