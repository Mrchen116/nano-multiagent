"""Public stop regressions for forced Gateway exit confirmation."""

from __future__ import annotations

import json
from pathlib import Path
import signal

import pytest

import personal_assistant.main as main_module
from personal_assistant.main import stop_gateway

from ._main_helpers import build_config


def _write_lifecycle_files(tmp_path: Path, *, with_state: bool) -> tuple[Path, Path]:
    pid_path = tmp_path / "gateway.pid"
    state_path = tmp_path / ".gateway-state.json"
    pid_path.write_text("2468", encoding="utf-8")
    if with_state:
        state_path.write_text(
            json.dumps(
                {
                    "pid": 2468,
                    "config_path": str(tmp_path / "node-config.yaml"),
                    "log_path": str(tmp_path / "gateway.log"),
                }
            ),
            encoding="utf-8",
        )
    return pid_path, state_path


@pytest.mark.parametrize("with_state", [False, True])
def test_force_stop_treats_sigkill_esrch_as_confirmed_exit(
    with_state: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    pid_path, state_path = _write_lifecycle_files(tmp_path, with_state=with_state)
    signals: list[tuple[str, int]] = []

    monkeypatch.setattr(main_module, "_pid_is_running", lambda _pid: True)

    def _kill(_pid: int, sig: int) -> None:
        signals.append(("pid", sig))
        if sig == signal.SIGKILL:
            raise ProcessLookupError

    monkeypatch.setattr(main_module.os, "kill", _kill)
    monkeypatch.setattr(
        main_module,
        "_kill_process_tree",
        lambda _pid, sig: signals.append(("group", sig)),
    )
    monkeypatch.setattr(main_module.time, "monotonic", iter([0.0, 1.0]).__next__)

    result = stop_gateway(
        config_path=config.source_path, load_config=lambda _path: config
    )

    assert "forced=true" in result
    assert signals == [
        ("pid", signal.SIGTERM),
        ("group", signal.SIGTERM),
        ("pid", signal.SIGKILL),
    ]
    assert not pid_path.exists()
    assert not state_path.exists()


@pytest.mark.parametrize("with_state", [False, True])
def test_force_stop_retains_lifecycle_state_when_process_survives_sigkill(
    with_state: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    pid_path, state_path = _write_lifecycle_files(tmp_path, with_state=with_state)
    signals: list[tuple[str, int]] = []
    clock = iter([0.0, 1.0, 2.0, 3.0])

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
    monkeypatch.setattr(main_module.time, "monotonic", clock.__next__)
    monkeypatch.setattr(main_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="did not exit after SIGKILL"):
        stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert signals == [
        ("pid", signal.SIGTERM),
        ("group", signal.SIGTERM),
        ("pid", signal.SIGKILL),
        ("group", signal.SIGKILL),
    ]
    assert pid_path.exists()
    assert state_path.exists() is with_state
