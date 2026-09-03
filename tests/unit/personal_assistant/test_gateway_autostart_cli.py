"""Operator-facing CLI behavior for Gateway autostart results."""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.gateway.process_lifecycle import GatewayLaunchResult
from personal_assistant.main import main


def test_main_reports_enabled_autostart_and_forwards_auto_bind(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    seen: dict[str, object] = {}

    def launch(**kwargs: object) -> GatewayLaunchResult:
        seen.update(kwargs)
        return GatewayLaunchResult(
            pid=123,
            log_path=tmp_path / "gateway.log",
            autostart_status="enabled",
        )

    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.launch_gateway_in_background",
        launch,
    )

    exit_code = main(["--config", str(tmp_path / "config.yaml"), "--auto-bind"])

    assert exit_code == 0
    assert seen["auto_bind"] is True
    assert "Autostart:       enabled" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        ["restart", "--auto-bind"],
        ["--auto-bind", "restart"],
    ],
)
def test_restart_accepts_auto_bind_on_either_side_of_subcommand(
    argv: list[str], monkeypatch, capsys, tmp_path: Path
) -> None:
    seen: dict[str, object] = {}

    def restart(**kwargs: object) -> GatewayLaunchResult:
        seen.update(kwargs)
        return GatewayLaunchResult(
            pid=4321,
            log_path=tmp_path / "gateway.log",
            autostart_status="enabled",
        )

    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.restart_gateway", restart
    )

    exit_code = main(argv)

    assert exit_code == 0
    assert seen["auto_bind"] is True
    assert "Autostart:       enabled" in capsys.readouterr().out


def test_main_reports_running_degraded_gateway_with_nonzero_exit(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.launch_gateway_in_background",
        lambda **_kwargs: GatewayLaunchResult(
            pid=123,
            log_path=tmp_path / "gateway.log",
            autostart_status="failed",
            autostart_error="bootstrap denied",
        ),
    )

    exit_code = main(["--config", str(tmp_path / "config.yaml")])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Gateway started (pid=123)" in captured.out
    assert "Autostart:       failed" in captured.out
    assert "bootstrap denied" in captured.err


def test_main_keeps_non_macos_output_unchanged(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.launch_gateway_in_background",
        lambda **_kwargs: GatewayLaunchResult(
            pid=123,
            log_path=tmp_path / "gateway.log",
            autostart_status="not_applicable",
        ),
    )

    assert main(["--config", str(tmp_path / "config.yaml")]) == 0
    assert "Autostart:" not in capsys.readouterr().out
