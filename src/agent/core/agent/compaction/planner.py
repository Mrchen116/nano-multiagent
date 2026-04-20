"""Compaction planner that selects safe history cut points."""

from typing import Sequence

from agent.core.session.entries import CompactionEntry, SessionEntry, SessionEntryKind

from .types import CompactionPlan, CompactionReason


class CompactionPlanner:
    """Plan compaction ranges while preserving critical tool-call/result integrity."""

    def __init__(self, *, min_kept_messages: int = 8) -> None:
        # min_kept_messages is retained for API compatibility with AgentRuntime
        # but is unused in the full-compact design (kept_events is always empty).
        del min_kept_messages

    def plan(
        self,
        *,
        events: Sequence[SessionEntry | CompactionEntry],
        reason: CompactionReason,
    ) -> CompactionPlan | None:
        """Build compaction plan for turn-appended events.

        Only summarizes events after the latest CompactionEntry to avoid
        re-summarizing already-compacted history.

        Args:
            events: Session events in chronological order.
            reason: Compaction trigger reason.

        Returns:
            A compaction plan when eligible, otherwise `None`.
        """

        # Find the latest CompactionEntry index so we only summarize new events.
        latest_compaction_idx = -1
        for i, event in enumerate(events):
            if isinstance(event, CompactionEntry):
                latest_compaction_idx = i

        turn_events = tuple(
            event
            for event in events[latest_compaction_idx + 1:]
            if isinstance(event, SessionEntry) and event.kind is SessionEntryKind.TURN_APPENDED
        )

        if not turn_events:
            return None

        # Boundary invariant: compaction cut must not split one tool call/result
        # pair across dropped and kept slices, otherwise replay context becomes
        # semantically inconsistent for subsequent model turns.
        # NOTE: kept_events is always empty in this design (full compact replaces
        # all old history with summary). The invariant is trivially satisfied.
        if _splits_tool_pair_across_boundary(turn_events):
            # Should not happen with empty kept_events, but keep as safeguard.
            return None

        return CompactionPlan(
            reason=reason,
            first_kept_event_id="",
            dropped_events=turn_events,
            kept_events=(),
        )


def _splits_tool_pair_across_boundary(turn_events: tuple[SessionEntry, ...]) -> bool:
    """Check if any tool call/result pair would be split.

    With kept_events always empty, this should always return False.
    Kept as a defensive check in case the design changes later.
    """
    call_ids: set[str] = set()
    result_ids: set[str] = set()
    for event in turn_events:
        phase, call_id = _tool_marker(event)
        if call_id is None:
            continue
        if phase == "call":
            call_ids.add(call_id)
        if phase == "result":
            result_ids.add(call_id)
    # A split would mean a call without result or result without call in dropped.
    return bool(call_ids.symmetric_difference(result_ids))


def _tool_marker(entry: SessionEntry) -> tuple[str | None, str | None]:
    metadata = entry.data.get("metadata")
    if not isinstance(metadata, dict):
        return None, None
    phase = metadata.get("tool_phase")
    call_id = metadata.get("tool_call_id")
    if not isinstance(phase, str) or not isinstance(call_id, str):
        return None, None
    return phase, call_id
