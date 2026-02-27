from nano_multiagent.session.manager import SessionManager

from .types import CompactionPlan, CompactionResult


class CompactionApplier:
    def __init__(self, *, session_manager: SessionManager) -> None:
        self._session_manager = session_manager

    def apply(
        self,
        *,
        session_id: str,
        plan: CompactionPlan,
        summary: str,
    ) -> CompactionResult:
        entry = self._session_manager.append_compaction(
            session_id,
            first_kept_event_id=plan.first_kept_event_id,
            summary=summary,
            data={"reason": plan.reason.value},
        )
        return CompactionResult(
            reason=plan.reason,
            entry_id=entry.entry_id,
            first_kept_event_id=entry.first_kept_event_id,
            summary=entry.summary,
            dropped_event_ids=tuple(event.entry_id for event in plan.dropped_events),
            kept_event_ids=tuple(event.entry_id for event in plan.kept_events),
        )
