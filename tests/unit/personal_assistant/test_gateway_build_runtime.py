"""Unit tests for build_runtime: PersistentSessionBindingStore wiring and token getter."""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    ChannelConfig,
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.gateway.session_keys import PersistentSessionBindingStore
from personal_assistant.main import GatewayStartupError, build_runtime

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


def test_build_runtime_uses_persistent_session_binding_store(
    tmp_path: Path,
) -> None:
    """build_runtime 构造的 pipeline 使用 PersistentSessionBindingStore。"""
    config = make_minimal_config(tmp_path)

    runtime = build_runtime(config)

    pipeline = runtime._on_inbound._pipeline  # noqa: SLF001
    assert isinstance(pipeline._session_store, PersistentSessionBindingStore)  # noqa: SLF001


def test_build_runtime_session_store_db_path_is_under_config_dir(
    tmp_path: Path,
) -> None:
    """session_bindings.sqlite3 与 relay_dedup.sqlite3 同目录（config_path 的父目录）。"""
    config = make_minimal_config(tmp_path)

    runtime = build_runtime(config)

    pipeline = runtime._on_inbound._pipeline  # noqa: SLF001
    store: PersistentSessionBindingStore = pipeline._session_store  # noqa: SLF001
    expected_db_path = tmp_path / "session_bindings.sqlite3"
    assert store._db_path == expected_db_path  # noqa: SLF001


def test_build_runtime_does_not_call_set_kernel_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """refactor-387 M3: build_runtime no longer calls set_kernel_client.

    Session validation is handled in-process via kernel.get_session inside
    InboundPipeline._binding_matches_workspace_root.  The old HTTP-based
    injection path is removed.
    """
    config = make_minimal_config(tmp_path)
    injected_clients: list[object] = []

    class _TrackingStore(PersistentSessionBindingStore):
        def set_kernel_client(self, client: object) -> None:
            injected_clients.append(client)
            super().set_kernel_client(client)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "personal_assistant.main.PersistentSessionBindingStore", _TrackingStore
    )

    build_runtime(config)

    assert len(injected_clients) == 0, (
        "M3: set_kernel_client must not be called — session validation is now in-process"
    )


def test_make_token_getter_is_importable() -> None:
    """_make_token_getter 应从 personal_assistant.main 可导入。"""
    from personal_assistant.main import _make_token_getter  # noqa: F401


@pytest.mark.asyncio
async def test_make_token_getter_uses_refresh_token_first(tmp_path: Path) -> None:
    """当 refresh_token 存在时，闭包应调用 IMAuthClient.refresh() 并返回新的 access_token。"""
    from personal_assistant.main import _make_token_getter
    from personal_assistant.config.local_store import (
        IMServiceConfig,
        LocalConfig,
        NodeConfig,
        KernelConfig,
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
        kernel=KernelConfig(),
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

    token_getter = _make_token_getter(
        im_service=im_service,
        local_config=local_config,
        auth_client=_FakeAuthClient(),
        save_config=_fake_save,
    )

    result = await token_getter()

    assert result == "new-access"
    # 新的 refresh_token 应已被持久化
    assert len(persisted) == 1
    assert persisted[0] == ("new-access", "new-refresh")


@pytest.mark.asyncio
async def test_make_token_getter_falls_back_to_login_when_refresh_fails(
    tmp_path: Path,
) -> None:
    """refresh 失败后应自动用 username+password 登录并返回 access_token。"""
    from personal_assistant.main import _make_token_getter
    from personal_assistant.auth.im_auth_client import IMAuthError
    from personal_assistant.config.local_store import (
        IMServiceConfig,
        LocalConfig,
        NodeConfig,
        KernelConfig,
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
        kernel=KernelConfig(),
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

    token_getter = _make_token_getter(
        im_service=im_service,
        local_config=local_config,
        auth_client=_FakeAuthClient(),
        save_config=_fake_save,
    )

    result = await token_getter()

    assert result == "login-access"
    assert len(persisted) == 1
    assert persisted[0] == ("login-access", "login-refresh")


@pytest.mark.asyncio
async def test_make_token_getter_returns_static_token_when_no_refresh_or_credentials(
    tmp_path: Path,
) -> None:
    """当 refresh_token/username/password 均未配置时，返回静态 config.token（向后兼容）。"""
    from personal_assistant.main import _make_token_getter
    from personal_assistant.config.local_store import (
        IMServiceConfig,
        LocalConfig,
        NodeConfig,
        KernelConfig,
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
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=im_service,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )

    token_getter = _make_token_getter(
        im_service=im_service,
        local_config=local_config,
        auth_client=_FakeAuthClient(),
        save_config=lambda cfg, path: None,
    )

    result = await token_getter()

    assert result == "static-token"


@pytest.mark.asyncio
async def test_reconcile_on_connect_continues_after_binding_failure_and_reports_degraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Binding failure during on_connected must not skip agent reconcile, and IM should
    receive a degraded heartbeat when the connected websocket can still send."""

    from personal_assistant import main as gateway_main

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace),),
        channels=(ChannelConfig(name="web_relay", enabled=True),),
        kernel=KernelConfig(),
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

        def reconcile_all_agents(
            self, *, memory_versions: dict[str, int] | None = None
        ) -> None:
            reconcile_calls.append(dict(memory_versions or {}))

    class _RecordingManager:
        connected = True

        def __init__(self) -> None:
            self.sent: list[tuple[str, dict[str, object]]] = []

        async def send_json(
            self, message_type: str, payload: dict[str, object]
        ) -> None:
            self.sent.append((message_type, dict(payload)))

        async def close(self) -> None:
            return None

    captured: dict[str, object] = {}
    manager = _RecordingManager()

    def _fake_build_im_connection_manager(**kwargs: object) -> object:
        captured.update(kwargs)
        return manager

    monkeypatch.setattr(gateway_main, "_IMBootstrapClient", _FailingBootstrap)
    monkeypatch.setattr(gateway_main, "_IMConfigSyncClient", _RecordingSyncClient)
    monkeypatch.setattr(
        gateway_main, "_build_im_connection_manager", _fake_build_im_connection_manager
    )

    build_runtime(config)
    on_connected = captured["on_connected"]

    await on_connected()

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
