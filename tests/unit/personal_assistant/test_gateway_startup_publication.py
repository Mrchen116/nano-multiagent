"""Gateway startup publication transaction regressions."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from agent.core.llm.model_registry import _reset_for_tests
from personal_assistant.main import (
    GatewayStartupError,
    RuntimeFactories,
    launch_gateway_in_background,
    run_gateway,
)
import personal_assistant.main as main_module

from ._main_helpers import _FakeProcess, build_config, write_gateway_identity


def test_background_state_publication_failure_reaps_child_and_clears_partial_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)
    state_path = tmp_path / ".gateway-state.json"

    def _fail_state_publication(_config, _result) -> None:  # noqa: ANN001
        state_path.write_text(
            json.dumps(
                {
                    "pid": 2468,
                    "config_path": str(config.source_path.resolve()),
                    "log_path": str(tmp_path / "gateway.log"),
                }
            ),
            encoding="utf-8",
        )
        raise OSError("state disk full")

    monkeypatch.setattr(main_module, "_write_gateway_state", _fail_state_publication)
    monkeypatch.setattr(main_module, "_kill_process_tree", lambda _pid, _sig: None)

    with pytest.raises(GatewayStartupError, match="state disk full") as raised:
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=lambda _argv, _log_path: process,
            wait_for_start=lambda _child, _config, _timeout: None,
        )

    assert isinstance(raised.value.__cause__, OSError)
    assert process.terminate_called == 1
    assert not state_path.exists()


def test_background_cleanup_failure_preserves_startup_and_cleanup_causes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(
        wait_result=subprocess.TimeoutExpired("gateway", 0.1), pid=2468
    )
    (tmp_path / "gateway.pid").write_text("2468", encoding="utf-8")
    write_gateway_identity(config)
    monkeypatch.setattr(main_module, "_kill_process_tree", lambda _pid, _sig: None)

    with pytest.raises(
        GatewayStartupError,
        match=r"cleanup.*pid=2468|pid=2468.*cleanup",
    ) as raised:
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=lambda _argv, _log_path: process,
            wait_for_start=lambda _child, _config, _timeout: (_ for _ in ()).throw(
                RuntimeError("startup confirmation failed")
            ),
        )

    cause = raised.value.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert [str(error) for error in cause.exceptions] == [
        "startup confirmation failed",
        "gateway pid=2468 did not exit after SIGKILL; lifecycle evidence retained",
    ]
    assert process.terminate_called == 1
    assert process.kill_called == 1
    assert (tmp_path / "gateway.pid").exists()
    assert (tmp_path / "gateway.identity.json").exists()


def test_foreground_identity_publication_failure_restores_signal_handlers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _reset_for_tests()
    config = build_config(tmp_path)
    restored: list[str] = []
    runtime_called: list[bool] = []

    class _Runtime:
        def run_forever(self) -> int:
            runtime_called.append(True)
            return 0

    monkeypatch.setattr(
        main_module,
        "_build_gateway_process_identity",
        lambda *_args, **_kwargs: main_module.GatewayProcessIdentity(
            schema_version=1,
            pid=2468,
            process_start="birth",
            config_path=str(config.source_path.resolve()),
            entry_module="personal_assistant.main",
            argv=("--config", str(config.source_path.resolve()), "--foreground"),
        ),
    )
    monkeypatch.setattr(
        main_module,
        "_write_gateway_process_identity",
        lambda _config, _identity: (_ for _ in ()).throw(
            OSError("identity fsync failed")
        ),
    )

    with pytest.raises(OSError, match="identity fsync failed"):
        run_gateway(
            config_path=config.source_path,
            factories=RuntimeFactories(
                load_config=lambda _path: config,
                build_runtime=lambda _config: _Runtime(),
                install_signal_handlers=lambda: lambda: restored.append("restored"),
            ),
        )

    assert restored == ["restored"]
    assert runtime_called == []
    assert not (tmp_path / "gateway.pid").exists()
    assert not (tmp_path / "gateway.identity.json").exists()


def test_foreground_pid_publication_failure_cleans_this_instance_and_restores_handlers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _reset_for_tests()
    config = build_config(tmp_path)
    restored: list[str] = []
    runtime_called: list[bool] = []
    identity = main_module.GatewayProcessIdentity(
        schema_version=1,
        pid=2468,
        process_start="birth",
        config_path=str(config.source_path.resolve()),
        entry_module="personal_assistant.main",
        argv=("--config", str(config.source_path.resolve()), "--foreground"),
    )
    original_write_pid = main_module._write_gateway_pid

    monkeypatch.setattr(
        main_module,
        "_build_gateway_process_identity",
        lambda *_args, **_kwargs: identity,
    )

    def _publish_then_fail(config, *, expected_pid=None) -> None:  # noqa: ANN001
        original_write_pid(config, expected_pid=expected_pid)
        raise OSError("pid directory fsync failed")

    monkeypatch.setattr(main_module, "_write_gateway_pid", _publish_then_fail)

    class _Runtime:
        def run_forever(self) -> int:
            runtime_called.append(True)
            return 0

    with pytest.raises(OSError, match="pid directory fsync failed"):
        run_gateway(
            config_path=config.source_path,
            factories=RuntimeFactories(
                load_config=lambda _path: config,
                build_runtime=lambda _config: _Runtime(),
                install_signal_handlers=lambda: lambda: restored.append("restored"),
            ),
        )

    assert restored == ["restored"]
    assert runtime_called == []
    assert not (tmp_path / "gateway.pid").exists()
    assert not (tmp_path / "gateway.identity.json").exists()
    assert not list(tmp_path.glob(".gateway.pid.*"))
