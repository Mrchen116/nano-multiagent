"""Red tests for feat-394-M7 R1: RunOrigin.CRON + submit_message mapping + _UNATTENDED_ORIGINS.

These tests verify:
1. RunOrigin.CRON exists and has value "cron"
2. _KernelClientShim.submit_message maps origin="cron" → RunOrigin.CRON
3. auto_mode_gate._UNATTENDED_ORIGINS includes RunOrigin.CRON.value ("cron")
"""

from __future__ import annotations

import pytest

from agent.core.runs.origin import RunOrigin


def test_run_origin_has_cron_value() -> None:
    """RunOrigin must have CRON = "cron" for feat-394-M7 R5-1 fix."""
    assert RunOrigin.CRON == "cron", (
        "RunOrigin.CRON must exist and equal 'cron'; "
        "without it, submit_message crashes with AttributeError"
    )


def test_run_origin_cron_is_str_enum() -> None:
    """RunOrigin.CRON must be usable as a string in frozenset comparisons."""
    assert RunOrigin.CRON.value == "cron"
    assert str(RunOrigin.CRON) == "cron"


def test_unattended_origins_includes_cron() -> None:
    """auto_mode_gate._UNATTENDED_ORIGINS must include 'cron' so cron runs bypass tool classifier ask."""
    from agent.platform.hooks.builtins.auto_mode_gate import _UNATTENDED_ORIGINS  # noqa: PLC2701

    assert "cron" in _UNATTENDED_ORIGINS, (
        "_UNATTENDED_ORIGINS must include 'cron'; "
        "without it, cron tool calls (during cron run execution) trigger classifier ask "
        "which has no human to answer — the run blocks indefinitely"
    )
    assert RunOrigin.CRON.value in _UNATTENDED_ORIGINS


def test_submit_message_maps_cron_origin(tmp_path: "Path") -> None:  # noqa: F821
    """_KernelClientShim.submit_message must map origin='cron' → RunOrigin.CRON without AttributeError."""
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    from personal_assistant.main import _KernelClientShim  # noqa: PLC2701

    captured_origin: list[RunOrigin] = []

    def _fake_submit(
        *,
        session_id: str,
        parts: list,
        origin: RunOrigin | None = None,
        workspace_root=None,
    ) -> object:
        captured_origin.append(origin)
        return MagicMock(run_id="run_test123")

    mock_kernel = MagicMock()
    mock_kernel.submit.side_effect = _fake_submit

    shim = _KernelClientShim(mock_kernel)

    # Must not raise AttributeError: type object 'RunOrigin' has no attribute 'SYSTEM'
    result = shim.submit_message(
        session_id="sess_abc",
        texts=["report current time"],
        workspace_root=str(tmp_path),
        origin="cron",
    )

    assert len(captured_origin) == 1
    assert captured_origin[0] is RunOrigin.CRON, (
        f"Expected RunOrigin.CRON but got {captured_origin[0]!r}"
    )
    assert result["run_id"] == "run_test123"
