"""Persist compaction summary and translate it into API-level result."""

from collections.abc import Sequence

from agent.core.session.manager import SessionManager

from .types import CompactionPlan, CompactionResult


class CompactionApplier:
    """Apply a compaction plan to session storage."""

    def __init__(self, *, session_manager: SessionManager) -> None:
        self._session_manager = session_manager

    def apply(
        self,
        *,
        session_id: str,
        plan: CompactionPlan,
        summary: str,
        restored_files: Sequence[str] = (),
    ) -> CompactionResult:
        """Persist compaction record and return normalized result.

        Args:
            session_id: Target session id.
            plan: Selected compaction plan.
            summary: Generated summary for dropped history.
            restored_files: Post-compact restored file contents (max 5).

        Returns:
            Persisted compaction result.

        Side Effects:
            Appends one compaction entry to the session store.
        """

        entry = self._session_manager.append_compaction(
            session_id,
            first_kept_event_id=plan.first_kept_event_id,
            summary=summary,
            data={
                "reason": plan.reason.value,
                "restored_files": list(restored_files),
            },
        )
        return CompactionResult(
            reason=plan.reason,
            entry_id=entry.entry_id,
            first_kept_event_id=entry.first_kept_event_id,
            summary=entry.summary,
            dropped_event_ids=tuple(event.entry_id for event in plan.dropped_events),
            kept_event_ids=(),
        )
