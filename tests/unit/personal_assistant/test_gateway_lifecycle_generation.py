"""Regression tests for public Gateway lifecycle generation ownership."""

from __future__ import annotations

import json
from pathlib import Path
import threading

import pytest

import personal_assistant.main as main_module

from ._main_helpers import _FakeProcess, build_config, write_gateway_identity


def _write_runtime_state(root: Path, config_path: Path, *, pid: int) -> None:
    (root / ".gateway-state.json").write_text(
        json.dumps(
            {
                "pid": pid,
                "config_path": str(config_path.resolve()),
                "log_path": str(root / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )


def _stub_owned_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    owned = main_module.GatewayOwnedProcessSet(
        leader_pid=2468,
        processes=(
            main_module.GatewayOwnedProcess(
                pid=2468,
                ppid=1,
                pgid=2468,
                process_start="Mon Jul 13 12:34:56 2026",
            ),
        ),
    )
    monkeypatch.setattr(
        main_module,
        "freeze_gateway_owned_process_set",
        lambda *_args, **_kwargs: owned,
    )
    monkeypatch.setattr(
        main_module,
        "signal_gateway_owned_process_set",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        main_module,
        "resume_gateway_owned_process_set",
        lambda _owned: None,
    )


def test_public_stop_serializes_replacement_start_for_same_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    _write_runtime_state(tmp_path, config.source_path, pid=2468)
    (tmp_path / "gateway.pid").write_text("2468", encoding="utf-8")
    write_gateway_identity(config)
    stop_waiting = threading.Event()
    release_stop = threading.Event()
    replacement_spawned = threading.Event()
    errors: list[BaseException] = []

    monkeypatch.setattr(main_module, "_assert_gateway_process_instance", lambda _: True)
    monkeypatch.setattr(main_module, "_kill_process_tree", lambda *_args: None)
    monkeypatch.setattr(main_module, "_pid_is_running", lambda _pid: False)
    monkeypatch.setattr(
        main_module, "_confirm_gateway_launch_publication", lambda *_args: None
    )
    _stub_owned_signals(monkeypatch)

    def _wait_for_exit(_config, _owned) -> bool:  # noqa: ANN001
        stop_waiting.set()
        assert release_stop.wait(timeout=2)
        return True

    def _spawn(_argv: list[str], _log_path: Path) -> _FakeProcess:
        replacement_spawned.set()
        (tmp_path / "gateway.pid").write_text("9753", encoding="utf-8")
        write_gateway_identity(config, pid=9753, process_start="replacement birth")
        return _FakeProcess(wait_result=0, pid=9753)

    monkeypatch.setattr(
        main_module, "_wait_for_gateway_owned_process_set_exit", _wait_for_exit
    )

    def _run_stop() -> None:
        try:
            main_module.stop_gateway(
                config_path=config.source_path,
                load_config=lambda _path: config,
            )
        except BaseException as exc:  # pragma: no cover - asserted by parent thread
            errors.append(exc)

    def _run_start() -> None:
        try:
            main_module.launch_gateway_in_background(
                config_path=config.source_path,
                load_config=lambda _path: config,
                spawn_process=_spawn,
                wait_for_start=lambda *_args: None,
            )
        except BaseException as exc:  # pragma: no cover - asserted by parent thread
            errors.append(exc)

    stop_thread = threading.Thread(target=_run_stop)
    start_thread = threading.Thread(target=_run_start)
    stop_thread.start()
    assert stop_waiting.wait(timeout=2)
    start_thread.start()
    start_crossed_old_generation = replacement_spawned.wait(timeout=0.2)
    release_stop.set()
    stop_thread.join(timeout=2)
    start_thread.join(timeout=2)

    assert not start_crossed_old_generation
    assert not stop_thread.is_alive()
    assert not start_thread.is_alive()
    assert errors == []
    assert json.loads((tmp_path / ".gateway-state.json").read_text())["pid"] == 9753
    assert (tmp_path / "gateway.pid").read_text(encoding="utf-8") == "9753"


def test_old_stop_cleanup_preserves_replacement_evidence_revision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    state_path = tmp_path / ".gateway-state.json"
    pid_path = tmp_path / "gateway.pid"
    identity_path = write_gateway_identity(config)
    _write_runtime_state(tmp_path, config.source_path, pid=2468)
    pid_path.write_text("2468", encoding="utf-8")

    monkeypatch.setattr(main_module, "_assert_gateway_process_instance", lambda _: True)
    monkeypatch.setattr(main_module, "_kill_process_tree", lambda *_args: None)
    _stub_owned_signals(monkeypatch)

    def _replace_generation(_config, _owned) -> bool:  # noqa: ANN001
        _write_runtime_state(tmp_path, config.source_path, pid=9753)
        pid_path.write_text("9753", encoding="utf-8")
        write_gateway_identity(config, pid=9753, process_start="replacement birth")
        return True

    monkeypatch.setattr(
        main_module,
        "_wait_for_gateway_owned_process_set_exit",
        _replace_generation,
    )

    result = main_module.stop_gateway(
        config_path=config.source_path,
        load_config=lambda _path: config,
    )

    assert result == f"STOPPED pid=2468 state={state_path}"
    assert json.loads(state_path.read_text(encoding="utf-8"))["pid"] == 9753
    assert pid_path.read_text(encoding="utf-8") == "9753"
    assert json.loads(identity_path.read_text(encoding="utf-8"))["pid"] == 9753
