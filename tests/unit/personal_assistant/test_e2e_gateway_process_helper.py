"""Regression tests for the critical-path Gateway process helper."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from tests.e2e.critical_paths import _im_gateway


class _RunningProcess:
    pid = 43210

    def poll(self) -> None:
        return None


@pytest.mark.parametrize(
    ("gateway_entrypoint", "expected_tail"),
    (
        (None, ["-m", "personal_assistant.main"]),
        ("/tmp/custom-gateway.py", ["/tmp/custom-gateway.py"]),
    ),
)
def test_restart_gateway_uses_current_pytest_interpreter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gateway_entrypoint: str | None,
    expected_tail: list[str],
) -> None:
    """Replacement Gateways stay in the same environment as the E2E runner."""
    (tmp_path / ".gateway-config.yaml").write_text("node: {}\n", encoding="utf-8")
    recorded: dict[str, object] = {}

    def _popen(command: list[str], **kwargs: object) -> _RunningProcess:
        recorded["command"] = command
        recorded["kwargs"] = kwargs
        return _RunningProcess()

    monkeypatch.setattr(_im_gateway.subprocess, "Popen", _popen)

    _im_gateway.restart_gateway(
        str(tmp_path),
        "54321",
        gateway_entrypoint=gateway_entrypoint,
    )

    command = recorded["command"]
    assert isinstance(command, list)
    assert command[: 1 + len(expected_tail)] == [sys.executable, *expected_tail]
