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
from personal_assistant.builtin_skills.lark_bundle import lark_skill_names
from personal_assistant.gateway.process_lifecycle import (
    GatewayLaunchResult,
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


@pytest.fixture(autouse=True)
def _use_existing_detached_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep this legacy suite focused on the non-macOS detached launcher."""
    monkeypatch.setattr(
        "personal_assistant.gateway.process_lifecycle.sys.platform", "linux"
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

    assert result == GatewayLaunchResult(
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


def test_load_runtime_config_provisions_lark_bundle_before_composition(
    tmp_path: Path,
) -> None:
    """Gateway startup persists the Lark bundle before runtime composition."""
    (tmp_path / "agent-a").mkdir()
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

    def save_updated(updated: LocalConfig, path: Path) -> None:
        saved.append(updated)
        local_store.save_local_config(updated, path)

    loaded = local_store.load_gateway_runtime_config(
        config.source_path,
        load_config=lambda _path: config,
        save_config=save_updated,
    )

    assert loaded.agents[0].skills == ("memory", *lark_skill_names())
    assert loaded.agents[0].skills_selection_mode == "explicit_allowlist"
    assert saved == [loaded]
    persisted = local_store.load_local_config(config.source_path).agents[0]
    assert persisted.skills == loaded.agents[0].skills
    assert persisted.skills_selection_mode == "explicit_allowlist"


@pytest.mark.parametrize(
    "selection_mode", [None, "default_discovery", "explicit_allowlist"]
)
def test_load_runtime_config_keeps_empty_feishu_selection_unmaterialized(
    tmp_path: Path, selection_mode: str | None
) -> None:
    """Feishu startup preserves both discovery and explicit-zero selections."""
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-open",
                workspace_root=tmp_path / "agent-open",
                skills=(),
                skills_selection_mode=selection_mode,
            ),
        ),
        channels=(
            ChannelConfig(
                name="feishu:agent-open",
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

    assert loaded.agents[0].skills == ()
    assert loaded.agents[0].skills_selection_mode == selection_mode
    assert saved == []


def test_load_runtime_config_does_not_materialize_default_nonempty_selection(
    tmp_path: Path,
) -> None:
    config = LocalConfig(
        node=NodeConfig(node_id="node-default"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-default",
                workspace_root=tmp_path / "agent-default",
                skills=("memory",),
                skills_selection_mode="default_discovery",
            ),
        ),
        channels=(
            ChannelConfig(
                name="feishu:agent-default",
                settings={"appId": "cli_a", "appSecret": "s_a", "botOpenId": "ou_bot"},
            ),
        ),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-default.yaml",
    )
    saved: list[LocalConfig] = []

    loaded = local_store.load_gateway_runtime_config(
        config.source_path,
        load_config=lambda _path: config,
        save_config=lambda updated, _path: saved.append(updated),
    )

    assert loaded.agents[0].skills == ("memory",)
    assert loaded.agents[0].skills_selection_mode == "default_discovery"
    assert saved == []


def test_load_runtime_config_does_not_migrate_unchanged_legacy_allowlist(
    tmp_path: Path,
) -> None:
    complete_skills = ("memory", *lark_skill_names())
    config = LocalConfig(
        node=NodeConfig(node_id="node-complete"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-complete",
                workspace_root=tmp_path / "agent-complete",
                skills=complete_skills,
            ),
        ),
        channels=(
            ChannelConfig(
                name="feishu:agent-complete",
                settings={"appId": "cli_a", "appSecret": "s_a", "botOpenId": "ou_bot"},
            ),
        ),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-complete.yaml",
    )
    saved: list[LocalConfig] = []

    loaded = local_store.load_gateway_runtime_config(
        config.source_path,
        load_config=lambda _path: config,
        save_config=lambda updated, _path: saved.append(updated),
    )

    assert loaded.agents[0].skills == complete_skills
    assert loaded.agents[0].skills_selection_mode is None
    assert saved == []


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
