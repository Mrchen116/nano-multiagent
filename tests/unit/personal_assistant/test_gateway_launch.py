"""Unit tests for launch_gateway_in_background and im_service URL override."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    ChannelConfig,
    HeartbeatConfig,
    IMServiceConfig,
    GatewayLifecycleConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.gateway.process_lifecycle import (
    BackgroundLaunchResult,
    GatewayStartupError,
    launch_gateway_in_background,
)

import personal_assistant.config.local_store as local_store

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


def test_launch_gateway_in_background_spawns_foreground_child_and_waits_for_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle._process_start_identity",
        lambda _pid: "birth-2468",
    )

    def _spawn_process(argv: list[str], log_path: Path) -> _FakeProcess:
        seen["spawn"] = (argv, log_path)
        return process

    def _wait_for_start(
        child: _FakeProcess, loaded_config: LocalConfig, timeout_seconds: float
    ) -> None:
        seen["wait"] = (child, loaded_config, timeout_seconds)
        state_path = config.source_path.parent / ".gateway-state.json"
        state_path.write_text(
            json.dumps(
                {
                    "pid": process.pid,
                    "process_start": "birth-2468",
                    "config_path": str(config.source_path.resolve()),
                    "log_path": str(config.source_path.parent / "gateway.log"),
                }
            ),
            encoding="utf-8",
        )

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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=1357)
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle._process_start_identity",
        lambda _pid: "birth-1357",
    )

    def _spawn_process(argv: list[str], log_path: Path) -> _FakeProcess:
        seen["spawn"] = (argv, log_path)
        return process

    def _wait_for_start(
        child: _FakeProcess, loaded_config: LocalConfig, timeout_seconds: float
    ) -> None:
        seen["wait"] = (child, loaded_config, timeout_seconds)
        state_path = config.source_path.parent / ".gateway-state.json"
        state_path.write_text(
            json.dumps(
                {
                    "pid": process.pid,
                    "process_start": "birth-1357",
                    "config_path": str(config.source_path.resolve()),
                    "log_path": str(config.source_path.parent / "gateway.log"),
                }
            ),
            encoding="utf-8",
        )

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

    loaded = local_store.load_gateway_runtime_config(
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


def test_load_runtime_config_provisions_feishu_skill_before_composition(
    tmp_path: Path,
) -> None:
    """Gateway startup persists the Feishu skill before runtime composition."""
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=tmp_path / "agent-a",
                skills=("memory",),
            ),
        ),
        channels=(
            ChannelConfig(
                name="feishu:agent-a",
                settings={"appId": "cli_a", "appSecret": "s_a", "botOpenId": "ou_bot"},
            ),
        ),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )
    saved: list[LocalConfig] = []

    loaded = local_store.load_gateway_runtime_config(
        config.source_path,
        load_config=lambda _path: config,
        save_config=lambda updated, _path: saved.append(updated),
    )

    assert loaded.agents[0].skills == ("memory", "feishu-doc")
    assert saved == [loaded]


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
