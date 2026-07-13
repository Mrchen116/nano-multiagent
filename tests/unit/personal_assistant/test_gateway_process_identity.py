"""Public Gateway process-instance identity and stop-bound regressions."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import signal
from types import SimpleNamespace

import pytest

from agent.core.llm.model_registry import _reset_for_tests
from personal_assistant.config.local_store import GatewayLifecycleConfig
import personal_assistant.main as main_module
from personal_assistant.main import (
    GatewayStartupError,
    RuntimeFactories,
    launch_gateway_in_background,
    run_gateway,
    stop_gateway,
)

from ._main_helpers import _FakeProcess, build_config


_PROCESS_START = "Mon Jul 13 12:34:56 2026"


def _identity_payload(config_path: Path, *, process_start: str = _PROCESS_START):
    return {
        "schema_version": 1,
        "pid": 2468,
        "process_start": process_start,
        "config_path": str(config_path.resolve()),
        "entry_module": "personal_assistant.main",
        "argv": ["--config", str(config_path.resolve()), "--foreground"],
    }


def _write_lifecycle(
    tmp_path: Path,
    *,
    with_state: bool,
    with_identity: bool = True,
    process_start: str = _PROCESS_START,
) -> None:
    config_path = tmp_path / "node-config.yaml"
    (tmp_path / "gateway.pid").write_text("2468", encoding="utf-8")
    if with_state:
        (tmp_path / ".gateway-state.json").write_text(
            json.dumps(
                {
                    "pid": 2468,
                    "config_path": str(config_path.resolve()),
                    "log_path": str(tmp_path / "gateway.log"),
                }
            ),
            encoding="utf-8",
        )
    if with_identity:
        (tmp_path / "gateway.identity.json").write_text(
            json.dumps(_identity_payload(config_path, process_start=process_start)),
            encoding="utf-8",
        )


def _observed_gateway(config_path: Path, *, process_start: str = _PROCESS_START):
    return SimpleNamespace(
        pid=2468,
        process_start=process_start,
        command=(
            "python -m personal_assistant.main --config "
            f"{config_path.resolve()} --foreground"
        ),
    )


def test_foreground_runtime_persists_identity_before_entering_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _reset_for_tests()
    config = build_config(tmp_path)
    identity_path = tmp_path / "gateway.identity.json"
    observed: list[dict[str, object]] = []
    monkeypatch.setattr(
        main_module,
        "read_gateway_process_snapshot",
        lambda pid: SimpleNamespace(
            pid=pid, process_start=_PROCESS_START, command="python"
        ),
        raising=False,
    )

    class _Runtime:
        def run_forever(self) -> int:
            assert (tmp_path / "gateway.pid").read_text(encoding="utf-8") == str(
                main_module.os.getpid()
            )
            observed.append(json.loads(identity_path.read_text(encoding="utf-8")))
            return 0

    result = run_gateway(
        config_path=config.source_path,
        factories=RuntimeFactories(
            load_config=lambda _path: config,
            build_runtime=lambda _config: _Runtime(),
        ),
    )

    assert result == 0
    assert observed == [
        {
            "argv": ["--config", str(config.source_path.resolve()), "--foreground"],
            "config_path": str(config.source_path.resolve()),
            "entry_module": "personal_assistant.main",
            "pid": main_module.os.getpid(),
            "process_start": _PROCESS_START,
            "schema_version": 1,
        }
    ]
    assert not identity_path.exists()
    assert not (tmp_path / "gateway.pid").exists()


def test_stop_fails_closed_without_process_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    _write_lifecycle(tmp_path, with_state=False, with_identity=False)
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(main_module, "_pid_is_running", lambda _pid: True)
    monkeypatch.setattr(
        main_module.os, "kill", lambda pid, sig: signals.append((pid, sig))
    )
    monkeypatch.setattr(main_module, "_kill_process_tree", lambda _pid, _sig: None)
    monkeypatch.setattr(
        main_module.time, "monotonic", iter([0.0, 1.0, 2.0, 3.0]).__next__
    )
    monkeypatch.setattr(main_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="identity"):
        stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert signals == []
    assert (tmp_path / "gateway.pid").exists()
    assert not (tmp_path / ".gateway-state.json").exists()


@pytest.mark.parametrize("with_state", [False, True])
def test_stop_rejects_reused_pid_birth_identity_before_any_signal(
    with_state: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    _write_lifecycle(tmp_path, with_state=with_state)
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        main_module,
        "read_gateway_process_snapshot",
        lambda _pid: _observed_gateway(config.source_path, process_start="new birth"),
        raising=False,
    )
    monkeypatch.setattr(main_module, "_pid_is_running", lambda _pid: True)
    monkeypatch.setattr(
        main_module.os, "kill", lambda pid, sig: signals.append((pid, sig))
    )
    monkeypatch.setattr(main_module, "_kill_process_tree", lambda _pid, _sig: None)
    monkeypatch.setattr(
        main_module.time, "monotonic", iter([0.0, 1.0, 2.0, 3.0]).__next__
    )
    monkeypatch.setattr(main_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="identity mismatch"):
        stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert signals == []
    assert (tmp_path / "gateway.pid").exists()
    assert (tmp_path / "gateway.identity.json").exists()
    assert (tmp_path / ".gateway-state.json").exists() is with_state


def test_default_background_waiter_requires_process_identity(tmp_path: Path) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)

    def _spawn(_argv: list[str], _log_path: Path) -> _FakeProcess:
        (tmp_path / "gateway.pid").write_text("2468", encoding="utf-8")
        return process

    with pytest.raises(GatewayStartupError, match="identity"):
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=_spawn,
        )


def test_public_stop_bounds_both_wait_phases_to_remaining_grace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    config = replace(
        config,
        gateway=GatewayLifecycleConfig(
            startup_timeout_seconds=1,
            shutdown_grace_seconds=1,
            poll_interval_seconds=10,
        ),
    )
    _write_lifecycle(tmp_path, with_state=True)
    signals: list[tuple[str, int]] = []
    sleeps: list[float] = []
    now = 0.0

    def _sleep(seconds: float) -> None:
        nonlocal now
        sleeps.append(seconds)
        now += seconds

    monkeypatch.setattr(
        main_module,
        "read_gateway_process_snapshot",
        lambda _pid: _observed_gateway(config.source_path),
        raising=False,
    )
    monkeypatch.setattr(main_module, "_pid_is_running", lambda _pid: True)
    monkeypatch.setattr(
        main_module.os,
        "kill",
        lambda _pid, sig: signals.append(("pid", sig)),
    )
    monkeypatch.setattr(
        main_module,
        "_kill_process_tree",
        lambda _pid, sig: signals.append(("group", sig)),
    )
    monkeypatch.setattr(main_module.time, "monotonic", lambda: now)
    monkeypatch.setattr(main_module.time, "sleep", _sleep)

    with pytest.raises(RuntimeError, match="did not exit after SIGKILL"):
        stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert sleeps == [1, 1]
    assert signals == [
        ("group", signal.SIGTERM),
        ("group", signal.SIGKILL),
    ]


def test_legacy_state_matching_gateway_is_upgraded_before_public_stop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    _write_lifecycle(tmp_path, with_state=True, with_identity=False)
    state_path = tmp_path / ".gateway-state.json"
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    state_payload["health_url"] = "http://127.0.0.1:8011/openapi.json"
    state_path.write_text(json.dumps(state_payload), encoding="utf-8")
    signals: list[tuple[str, int]] = []
    pid_checks = iter([True, False])
    monkeypatch.setattr(
        main_module,
        "read_gateway_process_snapshot",
        lambda _pid: _observed_gateway(config.source_path),
    )
    monkeypatch.setattr(main_module, "_pid_is_running", lambda _pid: next(pid_checks))
    monkeypatch.setattr(
        main_module.os,
        "kill",
        lambda _pid, sig: signals.append(("pid", sig)),
    )
    monkeypatch.setattr(
        main_module,
        "_kill_process_tree",
        lambda _pid, sig: signals.append(("group", sig)),
    )
    monkeypatch.setattr(main_module.time, "monotonic", iter([0.0, 0.0]).__next__)
    monkeypatch.setattr(main_module.time, "sleep", lambda _seconds: None)

    result = stop_gateway(
        config_path=config.source_path, load_config=lambda _path: config
    )

    assert result == f"STOPPED pid=2468 state={state_path}"
    assert signals == [("group", signal.SIGTERM)]
    assert not (tmp_path / "gateway.pid").exists()
    assert not (tmp_path / "gateway.identity.json").exists()
    assert not state_path.exists()


def test_legacy_state_sleeper_pid_is_rejected_without_signal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    _write_lifecycle(tmp_path, with_state=True, with_identity=False)
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        main_module,
        "read_gateway_process_snapshot",
        lambda _pid: SimpleNamespace(
            pid=2468,
            process_start=_PROCESS_START,
            command="/bin/sleep 100",
        ),
    )
    monkeypatch.setattr(
        main_module.os, "kill", lambda pid, sig: signals.append((pid, sig))
    )

    with pytest.raises(RuntimeError, match="legacy Gateway identity mismatch"):
        stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert signals == []
    assert (tmp_path / "gateway.pid").exists()
    assert (tmp_path / ".gateway-state.json").exists()
    assert not (tmp_path / "gateway.identity.json").exists()
