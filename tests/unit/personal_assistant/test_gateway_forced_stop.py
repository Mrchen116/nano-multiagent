"""Public stop regressions for forced Gateway exit confirmation."""

from __future__ import annotations

import json
from pathlib import Path
import signal

import pytest

import personal_assistant.main as main_module
from personal_assistant.main import stop_gateway

from ._main_helpers import (
    build_config,
    gateway_process_snapshot,
    write_gateway_identity,
)


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


def _owned_gateway_set() -> main_module.GatewayOwnedProcessSet:
    """Return the frozen single-process ownership used by public-stop fakes."""
    return main_module.GatewayOwnedProcessSet(
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


@pytest.mark.parametrize("with_state", [False, True])
def test_force_stop_treats_disappearance_after_group_sigkill_as_confirmed_exit(
    with_state: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    pid_path, state_path = _write_lifecycle_files(tmp_path, with_state=with_state)
    write_gateway_identity(config)
    signals: list[tuple[str, int]] = []
    killed = False

    monkeypatch.setattr(
        main_module,
        "read_gateway_process_snapshot",
        lambda _pid: gateway_process_snapshot(config),
    )
    monkeypatch.setattr(
        main_module,
        "freeze_gateway_owned_process_set",
        lambda *_args, **_kwargs: _owned_gateway_set(),
    )

    def _signal_owned(
        _owned: main_module.GatewayOwnedProcessSet,
        sig: int,
        **_kwargs: object,
    ) -> None:
        nonlocal killed
        signals.append(("group", sig))
        if sig == signal.SIGKILL:
            killed = True

    monkeypatch.setattr(main_module, "signal_gateway_owned_process_set", _signal_owned)
    monkeypatch.setattr(
        main_module, "resume_gateway_owned_process_set", lambda _owned: None
    )
    monkeypatch.setattr(
        main_module,
        "_wait_for_gateway_owned_process_set_exit",
        lambda _config, _owned: killed,
    )

    result = stop_gateway(
        config_path=config.source_path, load_config=lambda _path: config
    )

    assert "forced=true" in result
    assert signals == [
        ("group", signal.SIGTERM),
        ("group", signal.SIGKILL),
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
    write_gateway_identity(config)
    signals: list[tuple[str, int]] = []

    monkeypatch.setattr(
        main_module,
        "read_gateway_process_snapshot",
        lambda _pid: gateway_process_snapshot(config),
    )
    monkeypatch.setattr(
        main_module,
        "freeze_gateway_owned_process_set",
        lambda *_args, **_kwargs: _owned_gateway_set(),
    )
    monkeypatch.setattr(
        main_module,
        "signal_gateway_owned_process_set",
        lambda _owned, sig, **_kwargs: signals.append(("group", sig)),
    )
    monkeypatch.setattr(
        main_module, "resume_gateway_owned_process_set", lambda _owned: None
    )
    monkeypatch.setattr(
        main_module,
        "_wait_for_gateway_owned_process_set_exit",
        lambda _config, _owned: False,
    )

    with pytest.raises(RuntimeError, match="did not exit after SIGKILL"):
        stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert signals == [
        ("group", signal.SIGTERM),
        ("group", signal.SIGKILL),
    ]
    assert pid_path.exists()
    assert state_path.exists() is with_state
