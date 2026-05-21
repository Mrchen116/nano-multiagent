"""Unit tests for gateway PID file management, stop_gateway, and single-instance protection."""

from __future__ import annotations

import json
import os
import signal
from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    HeartbeatConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.main import (
    GatewayStartupError,
    RuntimeFactories,
    launch_gateway_in_background,
    run_gateway,
    stop_gateway,
)

import personal_assistant.main as main_module

from ._main_helpers import _FakeProcess, build_config


def test_launch_gateway_in_background_writes_runtime_state_file(tmp_path: Path) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)

    launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=lambda _argv, _log_path: process,
        wait_for_ready=lambda _child, _config, _timeout: None,
    )

    state_path = tmp_path / ".gateway-state.json"
    assert state_path.exists() is True
    assert "2468" in state_path.read_text(encoding="utf-8")
    assert str(config.source_path) in state_path.read_text(encoding="utf-8")


def test_stop_gateway_reports_still_healthy_when_pid_is_stale_but_health_url_is_alive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    state_path = tmp_path / ".gateway-state.json"
    state_path.write_text(
        json.dumps(
            {
                "pid": 2468,
                "config_path": str(config.source_path),
                "health_url": "http://127.0.0.1:8100/v1/health",
                "log_path": str(tmp_path / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: False)
    monkeypatch.setattr("personal_assistant.main._healthcheck_reports_healthy", lambda _url: True)

    result = main_module.stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert result == (
        "STALE pid=2468 state="
        f"{state_path} health_url=http://127.0.0.1:8100/v1/health still_healthy=true"
    )
    assert state_path.exists() is False


def test_stop_gateway_only_reports_stopped_after_health_url_goes_down(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(),
        channels=(),
        kernel=KernelConfig(
            command="python -m agent.platform.http_api.app",
            startup_timeout_seconds=0.2,
            health_poll_interval_seconds=0.01,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        source_path=tmp_path / "node-config.yaml",
    )
    state_path = tmp_path / ".gateway-state.json"
    state_path.write_text(
        json.dumps(
            {
                "pid": 2468,
                "config_path": str(config.source_path),
                "health_url": "http://127.0.0.1:8100/v1/health",
                "log_path": str(tmp_path / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )
    pid_checks = iter([True, False])
    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: next(pid_checks))
    monkeypatch.setattr("personal_assistant.main.os.kill", lambda _pid, _sig: None)
    monkeypatch.setattr("personal_assistant.main.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("personal_assistant.main.time.monotonic", iter([0.0, 0.01]).__next__)
    verify_calls: list[tuple[str, float, float]] = []

    def _verify(health_url: str, *, timeout_seconds: float, sleep_seconds: float) -> bool:
        verify_calls.append((health_url, timeout_seconds, sleep_seconds))
        return False

    monkeypatch.setattr("personal_assistant.main._verify_stopped_health_url", _verify)

    result = main_module.stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert result == (
        "STOPPED pid=2468 state="
        f"{state_path} health_url=http://127.0.0.1:8100/v1/health still_healthy=true"
    )
    assert verify_calls == [("http://127.0.0.1:8100/v1/health", 0.1, 0.01)]
    assert state_path.exists() is False


def test_run_gateway_writes_pid_file_before_start_and_removes_on_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """run_gateway must write gateway.pid before the runtime starts and remove it on clean exit."""
    from personal_assistant.main import run_gateway, _gateway_pid_path

    config = build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_observed_during_run: list[bool] = []

    class _Runtime:
        def run_forever(self) -> int:
            pid_observed_during_run.append(pid_path.exists())
            return 0

    run_gateway(
        config_path=config.source_path,
        factories=RuntimeFactories(
            load_config=lambda _path: config,
            build_runtime=lambda _config: _Runtime(),
        ),
    )

    assert pid_observed_during_run == [True], "gateway.pid must exist while runtime is running"
    assert not pid_path.exists(), "gateway.pid must be removed after clean exit"


def test_run_gateway_removes_pid_file_even_when_runtime_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """run_gateway must remove gateway.pid even when the runtime raises an exception."""
    from personal_assistant.main import run_gateway, _gateway_pid_path

    config = build_config(tmp_path)
    pid_path = _gateway_pid_path(config)

    class _BrokenRuntime:
        def run_forever(self) -> int:
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_gateway(
            config_path=config.source_path,
            factories=RuntimeFactories(
                load_config=lambda _path: config,
                build_runtime=lambda _config: _BrokenRuntime(),
            ),
        )

    assert not pid_path.exists(), "gateway.pid must be cleaned up even on error"


def test_launch_background_refuses_to_start_when_pid_file_shows_live_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """launch_gateway_in_background must raise GatewayStartupError with PID when already running."""
    from personal_assistant.main import launch_gateway_in_background, _gateway_pid_path

    config = build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_path.write_text("12345", encoding="utf-8")

    # Simulate that PID 12345 is alive
    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: True)

    with pytest.raises(GatewayStartupError) as exc_info:
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
        )

    assert "12345" in str(exc_info.value), "error must mention the existing PID"
    assert pid_path.exists(), "stale pid file must be left intact when process is alive"


def test_launch_background_clears_stale_pid_file_when_process_dead(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """launch_gateway_in_background must remove a stale gateway.pid if process is no longer running."""
    from personal_assistant.main import launch_gateway_in_background, _gateway_pid_path

    config = build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_path.write_text("99999", encoding="utf-8")

    spawned: list[list[str]] = []

    def _spawn(argv: list[str], log_path: Path) -> _FakeProcess:
        spawned.append(argv)
        return _FakeProcess(wait_result=0, pid=1111)

    # Simulate that PID 99999 is dead
    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: False)

    launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=_spawn,
        wait_for_ready=lambda _child, _config, _timeout: None,
    )

    assert spawned, "gateway must have been spawned after stale PID cleanup"
    assert not pid_path.exists() or pid_path.read_text(encoding="utf-8") != "99999", (
        "stale PID content must have been replaced"
    )


def test_stop_gateway_removes_pid_file_on_successful_stop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """stop_gateway must delete gateway.pid after successfully stopping the process."""
    from personal_assistant.main import stop_gateway, _gateway_pid_path

    config = build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_path.write_text("2468", encoding="utf-8")

    # Also write state file so stop_gateway can find the PID
    state_path = tmp_path / ".gateway-state.json"
    state_path.write_text(
        json.dumps(
            {
                "pid": 2468,
                "config_path": str(config.source_path),
                "health_url": "http://127.0.0.1:8100/v1/health",
                "log_path": str(tmp_path / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )

    pid_checks = iter([True, False])
    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: next(pid_checks))
    monkeypatch.setattr("personal_assistant.main.os.kill", lambda _pid, _sig: None)
    monkeypatch.setattr("personal_assistant.main.time.sleep", lambda _s: None)
    monkeypatch.setattr("personal_assistant.main.time.monotonic", iter([0.0, 0.01]).__next__)
    monkeypatch.setattr("personal_assistant.main._verify_stopped_health_url", lambda *a, **kw: True)

    result = stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert "STOPPED" in result
    assert not pid_path.exists(), "gateway.pid must be removed after stop"


def test_stop_gateway_stops_foreground_pid_without_runtime_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """stop_gateway must stop a live PID-file-only gateway started in foreground mode."""
    from personal_assistant.main import stop_gateway, _gateway_pid_path

    config = build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_path.write_text("2468", encoding="utf-8")
    pid_checks = iter([True, False])
    kills: list[tuple[int, int]] = []

    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: next(pid_checks))
    monkeypatch.setattr("personal_assistant.main.os.kill", lambda pid, sig: kills.append((pid, sig)))
    monkeypatch.setattr("personal_assistant.main.time.sleep", lambda _s: None)
    monkeypatch.setattr("personal_assistant.main.time.monotonic", iter([0.0, 0.01]).__next__)

    result = stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert result == f"STOPPED pid=2468 pid_file={pid_path}"
    assert kills == [(2468, signal.SIGTERM)]
    assert not pid_path.exists()
