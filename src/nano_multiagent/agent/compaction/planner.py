from typing import Mapping, Sequence

from nano_multiagent.session.entries import SessionEntry, SessionEntryKind

from .types import CompactionPlan, CompactionReason


class CompactionPlanner:
    def __init__(self, *, min_kept_messages: int = 8) -> None:
        self._min_kept_messages = max(min_kept_messages, 1)

    def plan(
        self,
        *,
        events: Sequence[SessionEntry],
        reason: CompactionReason,
    ) -> CompactionPlan | None:
        turn_events = tuple(event for event in events if event.kind is SessionEntryKind.TURN_APPENDED)
        if len(turn_events) <= self._min_kept_messages:
            return None

        keep_start = len(turn_events) - self._min_kept_messages
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
