"""Public terminal run-status values exposed by ``agent.sdk``."""

from agent.sdk import TERMINAL_RUN_STATUSES


def test_terminal_run_statuses_expose_public_terminal_values() -> None:
    assert TERMINAL_RUN_STATUSES == frozenset({"completed", "failed", "cancelled"})
