"""Translate an applied compaction plan into an API-level result.

bugfix-437 decision 2: persistence moved entirely to the runtime direct-write
path (``_compact_session``), which writes ``compact_boundary`` + summary via the
session writer AND resets the in-process history cache. This builder is now a
pure result constructor with no storage side effects — keeping a second write
here was the source of the workspace-aware crash (the redundant
``append_compaction`` passed ``workspace_root=None``) and of a write/observe
drift.
"""

from collections.abc import Sequence

from .types import CompactionPlan, CompactionResult


class CompactionApplier:
    """Build a CompactionResult from an applied plan (no persistence)."""

    def apply(
        self,
        *,
        plan: CompactionPlan,
        summary: str,
        summary_uuid: str,
        restored_files: Sequence[str] = (),
    ) -> CompactionResult:
        """Construct the normalized compaction result.

        Args:
            plan: Selected compaction plan.
            summary: Generated summary for dropped history.
            summary_uuid: Message id of the summary turn written by the runtime
                direct-write path; used as ``entry_id`` so observers and the
                on-disk ``compact_boundary`` reference the same id.
            restored_files: Post-compact restored file contents (max 5).

        Returns:
            Normalized compaction result. No side effects.
        """

        del restored_files  # carried on the on-disk compact_boundary, not the result
        return CompactionResult(
            reason=plan.reason,
            entry_id=summary_uuid,
            first_kept_event_id=plan.first_kept_event_id,
            summary=summary,
            dropped_event_ids=tuple(event.entry_id for event in plan.dropped_events),
            kept_event_ids=(),
        )
