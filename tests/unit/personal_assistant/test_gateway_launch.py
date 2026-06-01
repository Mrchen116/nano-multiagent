"""Unit tests for launch_gateway_in_background and im_service URL override."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.main import (
    BackgroundLaunchResult,
    GatewayStartupError,
    launch_gateway_in_background,
)

import personal_assistant.main as main_module

from ._main_helpers import _FakeProcess, build_config

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


def test_launch_gateway_in_background_spawns_foreground_child_and_waits_for_ready(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)
    seen: dict[str, object] = {}

    def _spawn_process(argv: list[str], log_path: Path) -> _FakeProcess:
        seen["spawn"] = (argv, log_path)
        return process

    def _wait_for_ready(
        child: _FakeProcess, loaded_config: LocalConfig, timeout_seconds: float
    ) -> None:
        seen["wait"] = (child, loaded_config, timeout_seconds)

    result = launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda path: config if path == config.source_path else None,
        spawn_process=_spawn_process,
        wait_for_ready=_wait_for_ready,
    )

    assert result == BackgroundLaunchResult(
        pid=2468,
        # refactor-387 M3: kernel is in-process; health_url shows pid= when no IM service configured.
        health_url="pid=2468",
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
    assert seen["wait"] == (process, config, config.kernel.startup_timeout_seconds)


def test_launch_gateway_in_background_passes_im_service_override_to_child_and_runtime_config(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=1357)
    seen: dict[str, object] = {}

    def _spawn_process(argv: list[str], log_path: Path) -> _FakeProcess:
        seen["spawn"] = (argv, log_path)
        return process

    def _wait_for_ready(
        child: _FakeProcess, loaded_config: LocalConfig, timeout_seconds: float
    ) -> None:
        seen["wait"] = (child, loaded_config, timeout_seconds)

    result = launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=_spawn_process,
        wait_for_ready=_wait_for_ready,
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
        kernel=KernelConfig(),
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


def test_launch_gateway_in_background_stops_child_when_ready_wait_fails(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0)

    with pytest.raises(RuntimeError, match="not ready"):
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=lambda _argv, _log_path: process,
            wait_for_ready=lambda _child, _config, _timeout: (_ for _ in ()).throw(
                RuntimeError("not ready")
            ),
        )

    assert process.terminate_called == 1
