"""Behavior tests for the concrete macOS Gateway LaunchAgent owner."""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

import pytest

from personal_assistant.gateway import macos_launch_agent


class _Launchctl:
    def __init__(self, *, loaded: bool = False, unload_lag_probes: int = 0) -> None:
        self.loaded = loaded
        self.unload_lag_probes = unload_lag_probes
        self.pending_unload_probes = 0
        self.calls: list[tuple[str, ...]] = []
        self.bootstrap_payload: dict[str, object] | None = None

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(tuple(args))
        command = args[1]
        if command == "print" and args[2].count("/") == 1:
            return subprocess.CompletedProcess(args, 0, "domain", "")
        if command == "print":
            if self.pending_unload_probes:
                self.pending_unload_probes -= 1
                if not self.pending_unload_probes:
                    self.loaded = False
                return subprocess.CompletedProcess(args, 0, "loaded", "")
            return subprocess.CompletedProcess(
                args,
                0 if self.loaded else 113,
                "loaded" if self.loaded else "",
                "" if self.loaded else "Could not find service",
            )
        if command == "bootout":
            self.pending_unload_probes = self.unload_lag_probes
            if not self.pending_unload_probes:
                self.loaded = False
            return subprocess.CompletedProcess(args, 0, "", "")
        if command == "bootstrap":
            self.bootstrap_payload = plistlib.loads(Path(args[3]).read_bytes())
            self.loaded = True
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(args)


def _patch_runtime_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    launch_agents = tmp_path / "LaunchAgents"
    monkeypatch.setattr(
        macos_launch_agent, "_launch_agents_directory", lambda: launch_agents
    )
    monkeypatch.setattr(
        macos_launch_agent, "_python_executable", lambda: Path("/venv/bin/python")
    )
    monkeypatch.setattr(
        macos_launch_agent, "_source_root", lambda: Path("/checkout/src")
    )
    return launch_agents


def test_apply_persists_stable_definition_but_bootstraps_transient_controls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    launch_agents = _patch_runtime_paths(monkeypatch, tmp_path)
    launchctl = _Launchctl()
    monkeypatch.setattr(macos_launch_agent, "_run_launchctl", launchctl)
    config_path = tmp_path / "config.yaml"
    log_path = tmp_path / "gateway.log"

    macos_launch_agent.apply_and_start(
        config_path=config_path,
        log_path=log_path,
        shutdown_grace_seconds=2.2,
        auto_bind=True,
        im_service_url_override="http://im.once:8011",
    )

    stable_path = macos_launch_agent.plist_path_for_config(config_path)
    stable = plistlib.loads(stable_path.read_bytes())
    stable_args = stable["ProgramArguments"]
    assert stable_path.parent == launch_agents
    assert stable["KeepAlive"] is True
    assert stable["ExitTimeOut"] == 3
    assert stable["WorkingDirectory"] == "/checkout"
    assert stable["EnvironmentVariables"] == {"PYTHONPATH": "/checkout/src"}
    assert stable["StandardOutPath"] == str(log_path)
    assert "--auto-bind" not in stable_args
    assert "http://im.once:8011" not in stable_args

    transient = launchctl.bootstrap_payload
    assert transient is not None
    transient_args = transient["ProgramArguments"]
    assert "--auto-bind" in transient_args
    assert transient_args[-2:] == ["--im-service-url", "http://im.once:8011"]
    assert list(launch_agents.glob(".*.bootstrap.plist")) == []


def test_stop_current_login_is_idempotent_when_job_is_not_loaded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_runtime_paths(monkeypatch, tmp_path)
    launchctl = _Launchctl(loaded=False)
    monkeypatch.setattr(macos_launch_agent, "_run_launchctl", launchctl)

    assert (
        macos_launch_agent.stop_current_login(config_path=tmp_path / "config.yaml")
        is False
    )
    assert not any(call[1] == "bootout" for call in launchctl.calls)


def test_stop_current_login_waits_for_async_bootout_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_runtime_paths(monkeypatch, tmp_path)
    launchctl = _Launchctl(loaded=True, unload_lag_probes=1)
    monkeypatch.setattr(macos_launch_agent, "_run_launchctl", launchctl)

    assert (
        macos_launch_agent.stop_current_login(config_path=tmp_path / "config.yaml")
        is True
    )


def test_permanently_remove_keeps_definition_when_bootout_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_runtime_paths(monkeypatch, tmp_path)
    config_path = tmp_path / "config.yaml"
    stable_path = macos_launch_agent.plist_path_for_config(config_path)
    stable_path.parent.mkdir(parents=True)
    stable_path.write_text("retained", encoding="utf-8")

    def fail_bootout(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[1] == "print" and args[2].count("/") == 1:
            return subprocess.CompletedProcess(args, 0, "domain", "")
        if args[1] == "print":
            return subprocess.CompletedProcess(args, 0, "loaded", "")
        return subprocess.CompletedProcess(args, 5, "", "permission denied")

    monkeypatch.setattr(macos_launch_agent, "_run_launchctl", fail_bootout)

    with pytest.raises(RuntimeError, match="permission denied"):
        macos_launch_agent.permanently_remove(config_path=config_path)

    assert stable_path.read_text(encoding="utf-8") == "retained"
