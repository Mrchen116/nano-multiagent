"""Cron origin mapping through the personal-assistant kernel client."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from agent.core.runs.origin import RunOrigin
from personal_assistant.gateway.kernel_client import InProcessKernelClient


def test_submit_message_maps_cron_origin(tmp_path: Path) -> None:
    """Submit isolated cron work with the kernel's unattended cron origin."""

    captured: list[RunOrigin | None] = []

    def _submit(**kwargs: object) -> object:
        captured.append(kwargs.get("origin"))  # type: ignore[arg-type]
        return MagicMock(run_id="run-cron")

    kernel = MagicMock()
    kernel.submit.side_effect = _submit

    result = InProcessKernelClient(kernel).submit_message(
        session_id="session-cron",
        texts=["report current time"],
        workspace_root=str(tmp_path),
        origin="cron",
    )

    assert captured == [RunOrigin.CRON]
    assert result["run_id"] == "run-cron"
