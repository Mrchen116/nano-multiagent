"""Regression tests for public Gateway instance and descendant ownership."""

from __future__ import annotations

import json
from pathlib import Path
import signal

import pytest

import personal_assistant.main as main_module

from ._main_helpers import build_config, write_gateway_identity


def test_process_tree_signal_falls_back_to_pid_for_shared_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group_signals: list[tuple[int, int]] = []
    pid_signals: list[tuple[int, int]] = []
    monkeypatch.setattr(main_module.os, "getpgid", lambda _pid: 9000)
    monkeypatch.setattr(
        main_module.os,
        "killpg",
        lambda pgid, sent_signal: group_signals.append((pgid, sent_signal)),
    )
    monkeypatch.setattr(
        main_module.os,
        "kill",
        lambda pid, sent_signal: pid_signals.append((pid, sent_signal)),
    )

    main_module._kill_process_tree(2468, signal.SIGTERM)  # noqa: SLF001

    assert group_signals == []
    assert pid_signals == [(2468, signal.SIGTERM)]


def test_public_stop_waits_for_complete_owned_descendant_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    pid_path = tmp_path / "gateway.pid"
    state_path = tmp_path / ".gateway-state.json"
    pid_path.write_text("2468", encoding="utf-8")
    state_path.write_text(
        json.dumps(
            {
                "pid": 2468,
                "config_path": str(config.source_path),
                "log_path": str(tmp_path / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )
    write_gateway_identity(config)
    owned = main_module.GatewayOwnedProcessSet(
        leader_pid=2468,
        processes=(
            main_module.GatewayOwnedProcess(
                pid=2468,
                ppid=1,
                pgid=2468,
                process_start="Mon Jul 13 12:34:56 2026",
            ),
            main_module.GatewayOwnedProcess(
                pid=9753,
                ppid=2468,
                pgid=9753,
                process_start="Mon Jul 13 12:34:57 2026",
            ),
        ),
    )
    signals: list[int] = []
    exits = iter([False, True])
    monkeypatch.setattr(main_module, "_assert_gateway_process_instance", lambda _: True)
    monkeypatch.setattr(main_module, "_kill_process_tree", lambda *_args: None)
    monkeypatch.setattr(main_module, "_pid_is_running", lambda _pid: True)
    monkeypatch.setattr(
        main_module,
        "freeze_gateway_owned_process_set",
        lambda *_args, **_kwargs: owned,
        raising=False,
    )
    monkeypatch.setattr(
        main_module,
        "signal_gateway_owned_process_set",
        lambda _owned, sent_signal, **_kwargs: signals.append(sent_signal),
    )
    monkeypatch.setattr(
        main_module,
        "resume_gateway_owned_process_set",
        lambda _owned: signals.append(signal.SIGCONT),
    )
    monkeypatch.setattr(
        main_module,
        "_wait_for_gateway_owned_process_set_exit",
        lambda _config, _owned: next(exits),
        raising=False,
    )

    result = main_module.stop_gateway(
        config_path=config.source_path,
        load_config=lambda _path: config,
    )

    assert result == f"STOPPED pid=2468 state={state_path} forced=true"
    assert signals == [signal.SIGTERM, signal.SIGCONT, signal.SIGKILL]
    assert not pid_path.exists()
    assert not state_path.exists()


def test_runtime_instance_claim_rejects_second_holder(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"

    with main_module._gateway_runtime_instance_claim(config_path):  # noqa: SLF001
        with pytest.raises(main_module.GatewayStartupError, match="already running"):
            with main_module._gateway_runtime_instance_claim(config_path):  # noqa: SLF001
                pytest.fail("a second holder must never enter the instance claim")
