"""Unit tests for launch_gateway_in_background and im_service URL override."""

from __future__ import annotations

import sys
import json
from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    HeartbeatConfig,
    IMServiceConfig,
    GatewayLifecycleConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.main import (
    BackgroundLaunchResult,
    GatewayStartupError,
    launch_gateway_in_background,
)

import personal_assistant.main as main_module

from ._main_helpers import (
    _FakeProcess,
    build_config,
    gateway_process_snapshot,
    write_gateway_identity,
)

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

_DEFAULT_TEST_LLM = LLMConfigPayload(
    default_model="kimiCoding:K2.6",
    providers=(
        LLMProviderPayload(
            name="anthropic",
            base_url="http://127.0.0.1:4000",
            models=(
                LLMModelPayload(
                    name="kimiCoding:K2.6",
                    extra_request_body={"thinking": {"type": "adaptive"}},
                ),
            ),
        ),
    ),
)


def test_launch_gateway_in_background_spawns_foreground_child_and_waits_for_start(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)
    seen: dict[str, object] = {}

    def _spawn_process(argv: list[str], log_path: Path) -> _FakeProcess:
        seen["spawn"] = (argv, log_path)
        return process

    def _wait_for_start(
        child: _FakeProcess, loaded_config: LocalConfig, timeout_seconds: float
    ) -> None:
        seen["wait"] = (child, loaded_config, timeout_seconds)

    result = launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda path: config if path == config.source_path else None,
        spawn_process=_spawn_process,
        wait_for_start=_wait_for_start,
    )

    assert result == BackgroundLaunchResult(
        pid=2468,
        log_path=config.source_path.parent / "gateway.log",
    )
    assert seen["spawn"] == (
        [
            sys.executable,
            "-m",
            "personal_assistant.main",
            "--config",
            str(config.source_path),
            "--foreground",
        ],
        config.source_path.parent / "gateway.log",
    )
    assert seen["wait"] == (process, config, config.gateway.startup_timeout_seconds)


def test_launch_gateway_in_background_passes_im_service_override_to_child_and_runtime_config(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=1357)
    seen: dict[str, object] = {}

    def _spawn_process(argv: list[str], log_path: Path) -> _FakeProcess:
        seen["spawn"] = (argv, log_path)
        return process

    def _wait_for_start(
        child: _FakeProcess, loaded_config: LocalConfig, timeout_seconds: float
    ) -> None:
        seen["wait"] = (child, loaded_config, timeout_seconds)

    result = launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=_spawn_process,
        wait_for_start=_wait_for_start,
        im_service_url_override="http://im.remote:9011",
    )

    assert result.im_service_url == "http://im.remote:9011"
    assert seen["spawn"] == (
        [
            sys.executable,
            "-m",
            "personal_assistant.main",
            "--config",
            str(config.source_path),
            "--im-service-url",
            "http://im.remote:9011",
            "--foreground",
        ],
        config.source_path.parent / "gateway.log",
    )
    loaded_config = seen["wait"][1]
    assert loaded_config.im_service is not None
    assert loaded_config.im_service.url == "http://im.remote:9011"


def test_load_runtime_config_preserves_im_credentials_when_overriding_url(
    tmp_path: Path,
) -> None:
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(
            url="http://im.old:8011",
            token="access-token",
            refresh_token="refresh-token",
            username="nano",
            password="nano1234",
        ),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )

    loaded = main_module._load_runtime_config(
        config.source_path,
        load_config=lambda _path: config,
        im_service_url_override="http://im.remote:9011",
    )

    assert loaded.im_service is not None
    assert loaded.im_service.url == "http://im.remote:9011"
    assert loaded.im_service.token == "access-token"
    assert loaded.im_service.refresh_token == "refresh-token"
    assert loaded.im_service.username == "nano"
    assert loaded.im_service.password == "nano1234"


def test_launch_gateway_in_background_stops_child_when_start_confirmation_fails(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0)

    with pytest.raises(RuntimeError, match="not started"):
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=lambda _argv, _log_path: process,
            wait_for_start=lambda _child, _config, _timeout: (_ for _ in ()).throw(
                RuntimeError("not started")
            ),
        )

    assert process.terminate_called == 1


def test_launch_gateway_in_background_default_waiter_reports_child_early_exit(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=7, poll_result=7)

    with pytest.raises(GatewayStartupError, match="return code 7"):
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=lambda _argv, _log_path: process,
        )


def test_launch_gateway_in_background_default_waiter_times_out_without_pid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0)
    monkeypatch.setattr(main_module.time, "monotonic", iter([0.0, 1.0]).__next__)
    monkeypatch.setattr(main_module, "_kill_process_tree", lambda _pid, _sig: None)

    with pytest.raises(GatewayStartupError, match="pid or process identity"):
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=lambda _argv, _log_path: process,
        )

    assert process.terminate_called == 1


def test_launch_gateway_in_background_default_waiter_accepts_child_pid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)

    def _spawn(_argv: list[str], _log_path: Path) -> _FakeProcess:
        (tmp_path / "gateway.pid").write_text("2468", encoding="utf-8")
        write_gateway_identity(config)
        return process

    monkeypatch.setattr(
        main_module,
        "read_gateway_process_snapshot",
        lambda _pid: gateway_process_snapshot(config),
    )

    result = launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=_spawn,
    )

    assert result.pid == 2468
    assert json.loads((tmp_path / ".gateway-state.json").read_text())["pid"] == 2468


def test_launch_gateway_in_background_removes_malformed_pid_before_spawn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    pid_path = tmp_path / "gateway.pid"
    pid_path.write_text("not-a-pid", encoding="utf-8")
    process = _FakeProcess(wait_result=0, pid=2468)

    def _spawn(_argv: list[str], _log_path: Path) -> _FakeProcess:
        assert not pid_path.exists()
        pid_path.write_text("2468", encoding="utf-8")
        write_gateway_identity(config)
        return process

    monkeypatch.setattr(
        main_module,
        "read_gateway_process_snapshot",
        lambda _pid: gateway_process_snapshot(config),
    )

    result = launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=_spawn,
    )

    assert result.pid == 2468


@pytest.mark.parametrize("pid_text", ["not-a-pid", "9999"])
def test_launch_gateway_in_background_rejects_invalid_or_mismatched_child_pid(
    pid_text: str,
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)

    def _spawn(_argv: list[str], _log_path: Path) -> _FakeProcess:
        (tmp_path / "gateway.pid").write_text(pid_text, encoding="utf-8")
        return process

    with pytest.raises(GatewayStartupError, match="PID"):
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=_spawn,
        )

    assert not (tmp_path / ".gateway-state.json").exists()


def test_launch_gateway_in_background_rechecks_child_before_pid_success(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)

    class _ExitsDuringConfirmation(_FakeProcess):
        def __init__(self) -> None:
            super().__init__(wait_result=7, pid=2468)
            self._poll_results = iter([None, 7, 7])

        def poll(self) -> int | None:
            return next(self._poll_results)

    process = _ExitsDuringConfirmation()

    def _spawn(_argv: list[str], _log_path: Path) -> _FakeProcess:
        (tmp_path / "gateway.pid").write_text("2468", encoding="utf-8")
        return process

    with pytest.raises(GatewayStartupError, match="return code 7"):
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=_spawn,
        )

    assert not (tmp_path / ".gateway-state.json").exists()
