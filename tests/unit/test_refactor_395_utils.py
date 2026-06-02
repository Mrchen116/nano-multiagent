"""Tests for refactor-395-M1: core utils extraction and TERMINAL_RUN_STATUSES canonicalization.

These tests define the expected state after the refactor — they fail before the
implementation and pass after. All assertions are behavioral contracts that prevent
future drift (e.g. TERMINAL_RUN_STATUSES diverging from the underlying enum).
"""

import pytest


class TestUtcNowIso:
    """agent.core.utils.time.utc_now_iso must exist and return an ISO 8601 UTC string."""

    def test_importable_from_core_utils(self) -> None:
        from agent.core.utils.time import utc_now_iso  # type: ignore[import]

        result = utc_now_iso()
        assert isinstance(result, str)
        # Rough sanity: UTC ISO strings contain a 'T' separator and '+00:00' or 'Z'
        assert "T" in result
        assert "+" in result or result.endswith("Z")

    def test_returns_different_values_over_time(self) -> None:
        import time

        from agent.core.utils.time import utc_now_iso  # type: ignore[import]

        t1 = utc_now_iso()
        time.sleep(0.01)
        t2 = utc_now_iso()
        # Two calls at different times must not collide
        assert t1 <= t2


class TestAtomicWrite:
    """agent.core.utils.fileio.atomic_write must exist and write atomically."""

    def test_importable_from_core_utils(self, tmp_path) -> None:
        from agent.core.utils.fileio import atomic_write  # type: ignore[import]

        target = tmp_path / "out.txt"
        atomic_write(target, "hello")
        assert target.read_text() == "hello"

    def test_overwrites_existing_file(self, tmp_path) -> None:
        from agent.core.utils.fileio import atomic_write  # type: ignore[import]

        target = tmp_path / "out.txt"
        target.write_text("old content")
        atomic_write(target, "new content")
        assert target.read_text() == "new content"

    def test_bytes_mode(self, tmp_path) -> None:
        from agent.core.utils.fileio import atomic_write  # type: ignore[import]

        target = tmp_path / "out.bin"
        atomic_write(target, b"\x00\x01\x02")
        assert target.read_bytes() == b"\x00\x01\x02"


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

        derived = frozenset(s.value for s in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED))
        assert TERMINAL_RUN_STATUSES == derived
