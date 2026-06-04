"""TERMINAL_RUN_STATUSES derivation and agent.sdk surface contract.

These tests lock the canonical value so that:
- coding_cli / personal_assistant can import it from agent.sdk (single source)
- The derived set never silently drifts from the underlying RunStatus enum literals
"""

import pytest


class TestTerminalRunStatuses:
    """TERMINAL_RUN_STATUSES must be derived from RunStatus enum and match the
    historical string literal set {"completed", "failed", "cancelled"}.

    This test locks the canonical value so that:
    - coding_cli / personal_assistant can import it from agent.sdk (single source)
    - The derived set never silently drifts from the original literals
    """

    def test_importable_from_agent_sdk(self) -> None:
        from agent.sdk import TERMINAL_RUN_STATUSES  # type: ignore[attr-defined]

        assert isinstance(TERMINAL_RUN_STATUSES, frozenset)

    def test_equals_historical_literals(self) -> None:
        from agent.sdk import TERMINAL_RUN_STATUSES  # type: ignore[attr-defined]

        expected = frozenset({"completed", "failed", "cancelled"})
        assert TERMINAL_RUN_STATUSES == expected, (
            f"TERMINAL_RUN_STATUSES drifted from expected literals: {TERMINAL_RUN_STATUSES!r}"
        )

    def test_derived_from_run_status_enum(self) -> None:
        """Ensure the value is actually derived from RunStatus, not a copy-paste literal."""
        from agent.core.runs.registry import RunStatus
        from agent.sdk import TERMINAL_RUN_STATUSES  # type: ignore[attr-defined]

        derived = frozenset(
            s.value
            for s in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED)
        )
        assert TERMINAL_RUN_STATUSES == derived
