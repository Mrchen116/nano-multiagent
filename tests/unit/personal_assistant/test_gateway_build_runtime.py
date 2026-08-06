"""Unit tests for compose_gateway: PersistentSessionBindingStore wiring and token getter."""

from __future__ import annotations

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
from personal_assistant.gateway.session_keys import PersistentSessionBindingStore
from personal_assistant.gateway.im_bootstrap import GatewayStartupError
from personal_assistant.gateway.composition import compose_gateway

from ._main_helpers import make_minimal_config

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


def test_compose_gateway_uses_persistent_session_binding_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """compose_gateway constructs the production persistent binding repository."""
    config = make_minimal_config(tmp_path)
    created: list[PersistentSessionBindingStore] = []

    class _TrackingStore(PersistentSessionBindingStore):
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr(
        "personal_assistant.gateway.composition.PersistentSessionBindingStore",
        _TrackingStore,
    )

    compose_gateway(config)

    assert len(created) == 1
    assert isinstance(created[0], PersistentSessionBindingStore)


def test_compose_gateway_session_store_db_path_is_under_config_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """session_bindings.sqlite3 与 relay_dedup.sqlite3 同目录（config_path 的父目录）。"""
    config = make_minimal_config(tmp_path)
    paths: list[Path] = []

    class _TrackingStore(PersistentSessionBindingStore):
        def __init__(self, *, db_path: Path) -> None:
            paths.append(db_path)
            super().__init__(db_path=db_path)

    monkeypatch.setattr(
        "personal_assistant.gateway.composition.PersistentSessionBindingStore",
        _TrackingStore,
    )

    compose_gateway(config)

    expected_db_path = tmp_path / "session_bindings.sqlite3"
    assert paths == [expected_db_path]


def test_compose_gateway_does_not_provision_feishu_skill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Composition must not persist configuration before the Gateway process starts."""
    base = make_minimal_config(tmp_path)
    config = LocalConfig(
        node=base.node,
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=base.agents[0].workspace_root,
                skills=("memory",),
            ),
        ),
        channels=(
            ChannelConfig(
                name="feishu:agent-a",
                enabled=True,
                settings={
                    "appId": "cli_a",
                    "appSecret": "secret",
                    "botOpenId": "ou_bot",
                },
            ),
        ),
        gateway=base.gateway,
        heartbeat=base.heartbeat,
        im_service=None,
        llm=base.llm,
        source_path=base.source_path,
    )

    def _unexpected_save(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("compose_gateway must not provision Feishu configuration")

    monkeypatch.setattr(
        "personal_assistant.config.local_store.save_sensitive_local_config",
        _unexpected_save,
    )

    compose_gateway(config)


def test_compose_gateway_defers_cron_initial_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cron stale-run recovery belongs to the running Gateway lifecycle."""
    registrations: list[str] = []

    def _record_registration(_self: object) -> None:
        registrations.append("registered")

    monkeypatch.setattr(
        "personal_assistant.scheduler.cron_gateway_runtime.GatewayCronRuntime.register_configured_agents",
        _record_registration,
    )

    runtime = compose_gateway(make_minimal_config(tmp_path))

    assert registrations == []
    assert runtime._startup_collaborators  # noqa: SLF001


def test_compose_gateway_wires_external_delivery_without_im_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = make_minimal_config(tmp_path)
    config = LocalConfig(
        node=base.node,
        agents=base.agents,
        channels=(
            ChannelConfig(
                name="feishu:agent-a",
                enabled=True,
                settings={
                    "appId": "cli_a",
                    "appSecret": "secret",
                    "botOpenId": "ou_bot",
                },
            ),
        ),
        gateway=base.gateway,
        heartbeat=base.heartbeat,
        im_service=None,
        llm=base.llm,
        source_path=base.source_path,
    )

    from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

    coordinator_kwargs: list[dict[str, object]] = []

    def _capture_coordinator(**kwargs):  # noqa: ANN003, ANN202
        coordinator_kwargs.append(dict(kwargs))
        return SessionRunCoordinator(**kwargs)

    monkeypatch.setattr(
        "personal_assistant.gateway.composition.SessionRunCoordinator",
        _capture_coordinator,
    )

    compose_gateway(config)

    assert coordinator_kwargs[0]["kernel_event_observer"] is not None
    assert coordinator_kwargs[0]["bg_reply_sender"] is not None


@pytest.mark.asyncio
async def test_im_token_provider_uses_refresh_token_first(tmp_path: Path) -> None:
    """当 refresh_token 存在时，闭包应调用 IMAuthClient.refresh() 并返回新的 access_token。"""
    from personal_assistant.auth.im_auth_client import IMTokenProvider
    from personal_assistant.config.local_store import (
        IMServiceConfig,
        LocalConfig,
        NodeConfig,
        GatewayLifecycleConfig,
        HeartbeatConfig,
    )

    class _FakeAuthClient:
        async def refresh(self, refresh_token: str) -> tuple[str, str]:
            return "new-access", "new-refresh"

        async def login(self, *, username: str, password: str) -> tuple[str, str]:
            raise AssertionError(
                "login should not be called when refresh_token is present"
            )

    config_path = tmp_path / "config.yaml"
    workspace = tmp_path / "ws"
    workspace.mkdir()
    config_path.write_text("", encoding="utf-8")

    im_service = IMServiceConfig(
        url="http://localhost:8011",
        token="stale-access",
        refresh_token="valid-refresh",
    )
    local_config = LocalConfig(
        node=NodeConfig(node_id="n1"),
        agents=(AgentWorkspaceConfig(agent_id="a1", workspace_root=workspace),),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=im_service,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )

    persisted: list[tuple[str, str]] = []

    def _fake_save(cfg, path) -> None:  # noqa: ANN001
        if cfg.im_service is not None:
            persisted.append(
                (cfg.im_service.token or "", cfg.im_service.refresh_token or "")
            )

    token_getter = IMTokenProvider(
        im_service=im_service,
        local_config=local_config,
        auth_client=_FakeAuthClient(),
        save_config=_fake_save,
    )

    result = await token_getter.get_token()

    assert result == "new-access"
    # 新的 refresh_token 应已被持久化
    assert len(persisted) == 1
    assert persisted[0] == ("new-access", "new-refresh")


@pytest.mark.asyncio
async def test_im_token_provider_falls_back_to_login_when_refresh_fails(
    tmp_path: Path,
) -> None:
    """refresh 失败后应自动用 username+password 登录并返回 access_token。"""
    from personal_assistant.auth.im_auth_client import IMTokenProvider
    from personal_assistant.auth.im_auth_client import IMAuthError
    from personal_assistant.config.local_store import (
        IMServiceConfig,
        LocalConfig,
        NodeConfig,
        GatewayLifecycleConfig,
        HeartbeatConfig,
    )

    class _FakeAuthClient:
        async def refresh(self, refresh_token: str) -> tuple[str, str]:
            raise IMAuthError("token expired", status_code=401)

        async def login(self, *, username: str, password: str) -> tuple[str, str]:
            return "login-access", "login-refresh"

    config_path = tmp_path / "config.yaml"
    workspace = tmp_path / "ws"
    workspace.mkdir()
    config_path.write_text("", encoding="utf-8")

    im_service = IMServiceConfig(
        url="http://localhost:8011",
        refresh_token="expired-refresh",
        username="nano",
        password="nano1234",
    )
    local_config = LocalConfig(
        node=NodeConfig(node_id="n1"),
        agents=(AgentWorkspaceConfig(agent_id="a1", workspace_root=workspace),),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=im_service,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )

    persisted: list[tuple[str, str]] = []

    def _fake_save(cfg, path) -> None:  # noqa: ANN001
        if cfg.im_service is not None:
            persisted.append(
                (cfg.im_service.token or "", cfg.im_service.refresh_token or "")
            )

    token_getter = IMTokenProvider(
        im_service=im_service,
        local_config=local_config,
        auth_client=_FakeAuthClient(),
        save_config=_fake_save,
    )

    result = await token_getter.get_token()

    assert result == "login-access"
    assert len(persisted) == 1
    assert persisted[0] == ("login-access", "login-refresh")


@pytest.mark.asyncio
async def test_im_token_provider_returns_static_token_when_no_refresh_or_credentials(
    tmp_path: Path,
) -> None:
    """当 refresh_token/username/password 均未配置时，返回静态 config.token（向后兼容）。"""
    from personal_assistant.auth.im_auth_client import IMTokenProvider
    from personal_assistant.config.local_store import (
        IMServiceConfig,
        LocalConfig,
        NodeConfig,
        GatewayLifecycleConfig,
        HeartbeatConfig,
    )

    class _FakeAuthClient:
        async def refresh(self, refresh_token: str) -> tuple[str, str]:
            raise AssertionError("should not be called")

        async def login(self, *, username: str, password: str) -> tuple[str, str]:
            raise AssertionError("should not be called")

    config_path = tmp_path / "config.yaml"
    workspace = tmp_path / "ws"
    workspace.mkdir()
    config_path.write_text("", encoding="utf-8")

    im_service = IMServiceConfig(url="http://localhost:8011", token="static-token")
    local_config = LocalConfig(
        node=NodeConfig(node_id="n1"),
        agents=(AgentWorkspaceConfig(agent_id="a1", workspace_root=workspace),),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=im_service,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )

    token_getter = IMTokenProvider(
        im_service=im_service,
        local_config=local_config,
        auth_client=_FakeAuthClient(),
        save_config=lambda cfg, path: None,
    )

    result = await token_getter.get_token()

    assert result == "static-token"


@pytest.mark.asyncio
async def test_reconcile_on_connect_continues_after_binding_failure_and_reports_degraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Binding failure during on_connected must not skip agent reconcile, and IM should
    receive a degraded heartbeat when the connected websocket can still send."""

    from personal_assistant.gateway import composition as gateway_composition

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace),),
        channels=(ChannelConfig(name="web_relay", enabled=True),),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local:9000", token="tok"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "config.yaml",
    )

    reconcile_calls: list[dict[str, int]] = []

    class _FailingBootstrap:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            return None

        def ensure_node_binding(self, *, node_id: str) -> str | None:
            raise GatewayStartupError(
                summary=f"binding failed for {node_id}",
                next_step="Open the bind URL and confirm this node.",
            )

    class _RecordingSyncClient:
        on_agent_created = None

        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            return None

        def sync_agent(self, agent_id: str) -> None:  # noqa: ARG002
            return None

        def update_token(self, token: str) -> None:  # noqa: ARG002
            return None

        def current_agent_payload(self, *, agent_id: str) -> None:  # noqa: ARG002
            return None

        def handle_agent_create(self, payload: object) -> object:
            return payload

        def reconcile_all_agents(self, *, latest_memory_version: object) -> None:
            assert latest_memory_version is not None
            reconcile_calls.append({})

    captured: dict[str, object] = {}

    class _RecordingManager:
        connected = True

        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)
            self.sent: list[tuple[str, dict[str, object]]] = []

        async def send_json(
            self, message_type: str, payload: dict[str, object]
        ) -> None:
            self.sent.append((message_type, dict(payload)))

        async def close(self) -> None:
            return None

    manager = _RecordingManager()

    monkeypatch.setattr(
        "personal_assistant.gateway.im_bootstrap.IMBootstrapClient", _FailingBootstrap
    )
    monkeypatch.setattr(gateway_composition, "IMAgentConfigSync", _RecordingSyncClient)
    monkeypatch.setattr(gateway_composition, "IMConnectionManager", _RecordingManager)

    manager = compose_gateway(config)._im_connection_manager
    assert isinstance(manager, _RecordingManager)
    on_connected = captured["on_connected"]

    await on_connected(manager)
    bootstrap_task = on_connected.__self__._node_bootstrap_task  # type: ignore[attr-defined]  # noqa: SLF001
    assert bootstrap_task is not None
    await bootstrap_task
    reconcile_task = on_connected.__self__._agent_reconcile_task  # type: ignore[attr-defined]  # noqa: SLF001
    assert reconcile_task is not None
    await reconcile_task

    assert reconcile_calls == [{}]
    assert manager.sent == [
        (
            "node.heartbeat",
            {
                "node_id": "node-local",
                "status": "degraded",
                "agent_count": 1,
                "last_error": (
                    "binding failed for node-local; next step: Open the bind URL and "
                    "confirm this node."
                ),
            },
        )
    ]
