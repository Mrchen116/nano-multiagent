"""Unit tests for gateway PID file management, stop_gateway, and single-instance protection."""

from __future__ import annotations

import json
import os
import signal
from pathlib import Path

import pytest

from personal_assistant.main import (
    GatewayStartupError,
    RuntimeFactories,
    launch_gateway_in_background,
    run_gateway,
    stop_gateway,
)

from agent.core.llm.model_registry import _reset_for_tests
from ._main_helpers import _FakeProcess, build_config


def _write_state(config_path: Path, *, pid: int, process_start: str | None) -> Path:
    state_path = config_path.parent / ".gateway-state.json"
    state_path.write_text(
        json.dumps(
            {
                "pid": pid,
                "process_start": process_start,
                "config_path": str(config_path.resolve()),
                "log_path": str(config_path.parent / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )
    return state_path


def _gateway_command(config_path: Path) -> str:
    return (
        "/usr/bin/python -m personal_assistant.main --config "
        f"{config_path.resolve()} --foreground"
    )


def test_launch_gateway_in_background_writes_runtime_state_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)
    monkeypatch.setattr(
        "personal_assistant.main._process_start_identity", lambda _pid: "birth-2468"
    )

    launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=lambda _argv, _log_path: process,
        wait_for_start=lambda _child, _config, _timeout: None,
    )

    state_path = tmp_path / ".gateway-state.json"
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "config_path": str(config.source_path),
        "log_path": str(tmp_path / "gateway.log"),
        "pid": 2468,
        "process_start": "birth-2468",
    }


def test_run_gateway_writes_pid_file_before_start_and_removes_on_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """run_gateway must write gateway.pid before the runtime starts and remove it on clean exit."""
    from personal_assistant.main import (
        _gateway_pid_path,
        _gateway_state_path,
        _read_gateway_state,
        run_gateway,
    )

    _reset_for_tests()  # run_gateway calls init_model_registry; must start from clean state
    config = build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    state_path = _gateway_state_path(config)
    evidence_observed_during_run: list[tuple[bool, str | None]] = []

    class _Runtime:
        def run_forever(self) -> int:
            state = _read_gateway_state(state_path)
            evidence_observed_during_run.append(
                (pid_path.exists(), state.process_start if state is not None else None)
            )
            return 0

    run_gateway(
        config_path=config.source_path,
        factories=RuntimeFactories(
            load_config=lambda _path: config,
            build_runtime=lambda _config: _Runtime(),
        ),
    )

    assert evidence_observed_during_run[0][0] is True
    assert evidence_observed_during_run[0][1]
    assert not pid_path.exists()
    assert not state_path.exists()


def test_run_gateway_removes_pid_file_even_when_runtime_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """run_gateway must remove gateway.pid even when the runtime raises an exception."""
    from personal_assistant.main import run_gateway, _gateway_pid_path

    _reset_for_tests()  # run_gateway calls init_model_registry; must start from clean state
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

    monkeypatch.setattr(
        "personal_assistant.main._process_start_identity", lambda _pid: "live-birth"
    )

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

    monkeypatch.setattr(
        "personal_assistant.main._process_start_identity",
        lambda pid: None if pid == 99999 else "new-birth",
    )

    launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=_spawn,
        wait_for_start=lambda _child, _config, _timeout: None,
    )

    assert spawned, "gateway must have been spawned after stale PID cleanup"
    assert not pid_path.exists() or pid_path.read_text(encoding="utf-8") != "99999", (
        "stale PID content must have been replaced"
    )


@pytest.mark.parametrize("stored_process_start", ["birth-a", None])
def test_stop_gateway_removes_pid_file_on_successful_stop(
    stored_process_start: str | None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """stop_gateway must delete gateway.pid after successfully stopping the process."""
    from personal_assistant.main import stop_gateway, _gateway_pid_path

    config = build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_path.write_text("2468", encoding="utf-8")
    state_path = _write_state(
        config.source_path, pid=2468, process_start=stored_process_start
    )

    running = True

    def _process_start(_pid: int) -> str | None:
        return "birth-a" if running else None

    def _kill_group(_pid: int, _sig: int) -> None:
        nonlocal running
        running = False

    monkeypatch.setattr(
        "personal_assistant.main._process_start_identity", _process_start
    )
    monkeypatch.setattr(
        "personal_assistant.main._process_command",
        lambda _pid: _gateway_command(config.source_path),
    )
    monkeypatch.setattr("personal_assistant.main.os.getpgid", lambda pid: pid)
    monkeypatch.setattr("personal_assistant.main.os.killpg", _kill_group)
    result = stop_gateway(
        config_path=config.source_path, load_config=lambda _path: config
    )

    assert "STOPPED" in result
    assert not pid_path.exists()
    assert not state_path.exists()


def test_stop_gateway_stops_foreground_pid_without_runtime_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """stop_gateway must stop a live PID-file-only gateway started in foreground mode."""
    from personal_assistant.main import stop_gateway, _gateway_pid_path

    config = build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_path.write_text("2468", encoding="utf-8")
    running = True
    kills: list[tuple[int, int]] = []

    def _process_start(_pid: int) -> str | None:
        return "birth-a" if running else None

    def _kill_group(pid: int, sig: int) -> None:
        nonlocal running
        kills.append((pid, sig))
        running = False

    monkeypatch.setattr(
        "personal_assistant.main._process_start_identity", _process_start
    )
    monkeypatch.setattr(
        "personal_assistant.main._process_command",
        lambda _pid: _gateway_command(config.source_path),
    )
    monkeypatch.setattr("personal_assistant.main.os.getpgid", lambda pid: pid)
    monkeypatch.setattr("personal_assistant.main.os.killpg", _kill_group)

    result = stop_gateway(
        config_path=config.source_path, load_config=lambda _path: config
    )

    assert result == f"STOPPED pid=2468 pid_file={pid_path}"
    assert kills == [(2468, signal.SIGTERM)]
    assert not pid_path.exists()


def test_stop_gateway_rejects_legacy_pid_owned_by_another_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    pid_path = tmp_path / "gateway.pid"
    pid_path.write_text("2468", encoding="utf-8")
    state_path = _write_state(config.source_path, pid=2468, process_start=None)
    monkeypatch.setattr(
        "personal_assistant.main._process_start_identity", lambda _pid: "birth-a"
    )
    monkeypatch.setattr(
        "personal_assistant.main._process_command", lambda _pid: "/bin/sleep 100"
    )
    monkeypatch.setattr(
        "personal_assistant.main.os.kill",
        lambda *_args: pytest.fail("an unrelated process must never receive a signal"),
    )
    monkeypatch.setattr(
        "personal_assistant.main.os.killpg",
        lambda *_args: pytest.fail("an unrelated process group must not be signalled"),
    )

    with pytest.raises(RuntimeError, match="ownership mismatch; evidence retained"):
        stop_gateway(
            config_path=config.source_path, load_config=lambda _path: config
        )

    assert pid_path.exists()
    assert json.loads(state_path.read_text(encoding="utf-8"))["process_start"] is None


def test_stop_gateway_does_not_signal_reused_pid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    pid_path = tmp_path / "gateway.pid"
    pid_path.write_text("2468", encoding="utf-8")
    state_path = _write_state(
        config.source_path, pid=2468, process_start="original-birth"
    )
    monkeypatch.setattr(
        "personal_assistant.main._process_start_identity",
        lambda _pid: "reused-birth",
    )
    monkeypatch.setattr(
        "personal_assistant.main.os.kill",
        lambda *_args: pytest.fail("a reused PID must never receive a signal"),
    )
    monkeypatch.setattr(
        "personal_assistant.main.os.killpg",
        lambda *_args: pytest.fail(
            "a reused process group must never receive a signal"
        ),
    )

    result = stop_gateway(
        config_path=config.source_path, load_config=lambda _path: config
    )

    assert result == f"STALE pid=2468 state={state_path}"
    assert not pid_path.exists()
    assert not state_path.exists()
