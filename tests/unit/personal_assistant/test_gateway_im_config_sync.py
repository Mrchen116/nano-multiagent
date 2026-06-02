"""Unit tests for _IMConfigSyncClient: profile polling, session drops, workspace seeding."""

from __future__ import annotations

from pathlib import Path

import httpx

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
    load_local_config,
)
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.main import _IMConfigSyncClient

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
                LLMModelPayload(name="claude-sonnet-4-6"),
            ),
        ),
    ),
)


def test_im_config_sync_client_retries_until_live_agent_config_reaches_target_version(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace-from-im"
    seen: list[tuple[str, str | None]] = []
    sleeps: list[float] = []
    responses = iter(
        [
            httpx.Response(404, json={"detail": "agent_id not found"}),
            httpx.Response(
                200,
                json={
                    "agent_id": "agent-live",
                    "display_name": "Agent Live",
                    "profile_version": 1,
                    "workspace_root": str(workspace_root),
                },
            ),
            httpx.Response(
                200,
                json={
                    "agent_id": "agent-live",
                    "display_name": "Agent Live v2",
                    "profile_version": 2,
                    "workspace_root": str(workspace_root),
                },
            ),
        ]
    )

    class _Pipeline:
        def __init__(self) -> None:
            self.dropped: list[str] = []

        def register_agent(self, agent: AgentWorkspaceConfig) -> None:
            seen.append((agent.agent_id, str(agent.workspace_root)))

        def drop_agent_sessions(self, agent_id: str) -> None:
            self.dropped.append(agent_id)

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/im/v1/agents/agent-live/config"
        assert request.url.params["source"] == "mirror"
        return next(responses)

    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://im.local",
        trust_env=False,
    )
    pipeline = _Pipeline()
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")
            ),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=pipeline,
        local_config=local_config,
        client=client,
        monotonic=lambda: 0.0,
        sleep=lambda seconds: sleeps.append(seconds),
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    assert seen == [("agent-live", str(workspace_root))]
    assert pipeline.dropped == ["agent-live"]
    assert sleeps == [0.1, 0.1]
    assert workspace_root.is_dir()
    # feat-349-M3: MEMORY.md/USER.md seed under .nanoassistant/memory/;
    # HEARTBEAT.md stays at workspace root.
    memory_seed = workspace_root / ".nanoassistant" / "memory" / "MEMORY.md"
    assert memory_seed.is_file() is True
    assert (workspace_root / "HEARTBEAT.md").is_file() is True
    assert memory_seed.read_text(encoding="utf-8").strip()
    assert (workspace_root / "HEARTBEAT.md").read_text(encoding="utf-8").strip()


def test_im_config_sync_client_drops_existing_agent_session_bindings_after_profile_refresh(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)

    class _Pipeline:
        def __init__(self) -> None:
            self.registered: list[tuple[str, str]] = []
            self._session_store = SessionBindingStore()
            self._session_store.bind(
                session_key="web:conv-1:agent-live",
                kernel_session_id="sess-old",
                reply_context=type(
                    "_ReplyContext",
                    (),
                    {
                        "channel_name": "web_relay",
                        "target_chat_id": "conv-1",
                        "thread_id": None,
                        "metadata": {},
                    },
                )(),
            )
            self._session_store.bind(
                session_key="web:conv-2:agent-other",
                kernel_session_id="sess-other",
                reply_context=type(
                    "_ReplyContext",
                    (),
                    {
                        "channel_name": "web_relay",
                        "target_chat_id": "conv-2",
                        "thread_id": None,
                        "metadata": {},
                    },
                )(),
            )

        def register_agent(self, agent: AgentWorkspaceConfig) -> None:
            self.registered.append((agent.agent_id, str(agent.workspace_root)))

        def drop_agent_sessions(self, agent_id: str) -> None:
            self._session_store.drop_agent(agent_id)

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/im/v1/agents/agent-live/config"
        return httpx.Response(
            200,
            json={
                "agent_id": "agent-live",
                "display_name": "Agent Live",
                "profile_version": 2,
            },
        )

    pipeline = _Pipeline()
    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://im.local",
        trust_env=False,
    )
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")
            ),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=pipeline,
        local_config=local_config,
        workspace_root_factory=lambda _agent_id: workspace_root,
        client=client,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    assert pipeline.registered == [("agent-live", str(workspace_root))]
    assert pipeline._session_store.get("web:conv-1:agent-live") is None
    assert pipeline._session_store.get("web:conv-2:agent-other") is not None


def test_im_config_sync_client_does_not_overwrite_existing_workspace_files(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    # feat-349-M3: MEMORY.md seeds under .nanoassistant/memory/; HEARTBEAT.md at root.
    memory_path = workspace_root / ".nanoassistant" / "memory" / "MEMORY.md"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_path = workspace_root / "HEARTBEAT.md"
    memory_path.write_text("existing memory\n", encoding="utf-8")
    heartbeat_path.write_text(
        "interval: 1h\n\n- Existing heartbeat\n", encoding="utf-8"
    )
    seen: list[tuple[str, str | None]] = []

    class _Pipeline:
        def __init__(self) -> None:
            self.dropped: list[str] = []

        def register_agent(self, agent: AgentWorkspaceConfig) -> None:
            seen.append((agent.agent_id, str(agent.workspace_root)))

        def drop_agent_sessions(self, agent_id: str) -> None:
            self.dropped.append(agent_id)

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/im/v1/agents/agent-live/config"
        return httpx.Response(
            200,
            json={
                "agent_id": "agent-live",
                "display_name": "Agent Live",
                "profile_version": 2,
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://im.local",
        trust_env=False,
    )
    pipeline = _Pipeline()
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")
            ),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=pipeline,
        local_config=local_config,
        workspace_root_factory=lambda _agent_id: workspace_root,
        client=client,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    assert seen == [("agent-live", str(workspace_root))]
    assert pipeline.dropped == ["agent-live"]
    assert memory_path.read_text(encoding="utf-8") == "existing memory\n"
    assert (
        heartbeat_path.read_text(encoding="utf-8")
        == "interval: 1h\n\n- Existing heartbeat\n"
    )


def test_im_config_sync_client_persists_agent_config_to_source_path(
    tmp_path: Path,
) -> None:
    """Config sync must write back to the path the config was loaded from, not a hardcoded default."""
    workspace_root = tmp_path / "workspace"

    class _Pipeline:
        def register_agent(self, agent: AgentWorkspaceConfig) -> None:
            self.agent = agent

        def drop_agent_sessions(self, agent_id: str) -> None:
            self.dropped = agent_id

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "agent-live",
                "display_name": "Agent Live",
                "profile_version": 2,
                "workspace_root": str(workspace_root),
                "skills": ["skill-a", "skill-b"],
                "tool_allowlist": ["Read", "Bash"],
                "system_prompt": "You are synced.",
                "group_reply_policy": "mention_only",
                "default_model": "claude-sonnet-4-6",
            },
        )

    seed_workspace = tmp_path / "seed-workspace"
    seed_workspace.mkdir(parents=True)
    config_path = tmp_path / "my-config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed-agent", workspace_root=seed_workspace),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=_Pipeline(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    # Must write to source_path (where the config was loaded from), not a hardcoded default.
    assert config_path.exists() is True
    persisted = load_local_config(config_path)
    assert persisted.source_path == config_path
    assert len(persisted.agents) == 2
    agent = next(item for item in persisted.agents if item.agent_id == "agent-live")
    assert agent.title == "Agent Live"
    assert agent.workspace_root == workspace_root.resolve()
    assert agent.skills == ("skill-a", "skill-b")
    assert agent.tool_allowlist == ("Read", "Bash")
    assert agent.system_prompt == "You are synced."
    assert agent.group_reply_policy == "mention_only"
    assert agent.default_model == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# feat-379-M2/R2: features + custom_prompt passthrough in sync/create/current
# ---------------------------------------------------------------------------


def _make_local_config(tmp_path: Path, workspace_root: Path) -> "LocalConfig":
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-r2"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed", workspace_root=(tmp_path / "seed")),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    return local_config


class _NullPipeline:
    registered: list["AgentWorkspaceConfig"] = []

    def register_agent(self, agent: "AgentWorkspaceConfig") -> None:
        self.registered.append(agent)

    def drop_agent_sessions(self, agent_id: str) -> None:
        pass


def test_sync_agent_passes_through_features(tmp_path: Path) -> None:
    """sync_agent must write features from IM payload into AgentWorkspaceConfig."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "alpha",
                "display_name": "Alpha",
                "profile_version": 1,
                "workspace_root": str(workspace_root),
                "features": {"memory_curation": False},
                "custom_prompt": "You are a legal advisor.",
            },
        )

    pipeline = _NullPipeline()
    pipeline.registered = []
    local_config = _make_local_config(tmp_path, workspace_root)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=pipeline,
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    sync.sync_agent(agent_id="alpha", profile_version=1)

    registered = next(a for a in pipeline.registered if a.agent_id == "alpha")
    # features must be passed through from IM payload
    assert registered.features.get("memory_curation") is False
    assert registered.custom_prompt == "You are a legal advisor."


def test_handle_agent_create_passes_through_features(tmp_path: Path) -> None:
    """handle_agent_create must include features + custom_prompt in the created AgentWorkspaceConfig."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()

    pipeline = _NullPipeline()
    pipeline.registered = []
    local_config = _make_local_config(tmp_path, workspace_root)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=pipeline,
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={})),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    result = sync.handle_agent_create(
        {
            "agent_id": "beta",
            "workspace_root": str(workspace_root),
            "features": {"skill_creation": False},
            "custom_prompt": "You are a chef.",
        }
    )

    # Return payload must include features + custom_prompt
    assert result["features"] == {"skill_creation": False}
    assert result["custom_prompt"] == "You are a chef."
    # Persisted agent config must include features + custom_prompt
    registered = next(a for a in pipeline.registered if a.agent_id == "beta")
    assert registered.features.get("skill_creation") is False
    assert registered.custom_prompt == "You are a chef."


# ---------------------------------------------------------------------------
# feat-394-M1/R5: heartbeat fields sync from IM → AgentWorkspaceConfig
# ---------------------------------------------------------------------------


def test_sync_agent_passes_through_heartbeat_enabled(tmp_path: Path) -> None:
    """sync_agent must write heartbeat_enabled from IM payload into AgentWorkspaceConfig.

    feat-394 decision 5: heartbeat config from AgentProfile in IM must flow to
    AgentWorkspaceConfig.heartbeat_enabled so the scheduler gate works correctly.
    """
    workspace_root = tmp_path / "ws-hb"
    workspace_root.mkdir()

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "hb-agent",
                "display_name": "HB Agent",
                "profile_version": 1,
                "workspace_root": str(workspace_root),
                "heartbeat": {"enabled": True, "every": "10m"},
            },
        )

    pipeline = _NullPipeline()
    pipeline.registered = []
    local_config = _make_local_config(tmp_path, workspace_root)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=pipeline,
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    sync.sync_agent(agent_id="hb-agent", profile_version=1)

    registered = next(a for a in pipeline.registered if a.agent_id == "hb-agent")
    assert registered.heartbeat_enabled is True
    assert registered.heartbeat_every == "10m"


def test_sync_agent_heartbeat_disabled_by_default(tmp_path: Path) -> None:
    """When IM payload has no heartbeat block, heartbeat_enabled must default to False."""
    workspace_root = tmp_path / "ws-no-hb"
    workspace_root.mkdir()

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "no-hb-agent",
                "display_name": "No HB",
                "profile_version": 1,
                "workspace_root": str(workspace_root),
            },
        )

    pipeline = _NullPipeline()
    pipeline.registered = []
    local_config = _make_local_config(tmp_path, workspace_root)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=pipeline,
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    sync.sync_agent(agent_id="no-hb-agent", profile_version=1)

    registered = next(a for a in pipeline.registered if a.agent_id == "no-hb-agent")
    assert registered.heartbeat_enabled is False


def test_current_agent_payload_includes_features(tmp_path: Path) -> None:
    """current_agent_payload must expose features + custom_prompt for capabilities reporting."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-r2"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="gamma",
                workspace_root=workspace_root,
                features={"memory_curation": True},
                custom_prompt="You are a tutor.",
            ),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=_NullPipeline(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={})),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    payload = sync.current_agent_payload(agent_id="gamma")
    assert payload is not None
    assert payload["features"] == {"memory_curation": True}
    assert payload["custom_prompt"] == "You are a tutor."


# ---------------------------------------------------------------------------
# feat-394-M3/R1: token_getter 修复 — auto-bind 后 token 刷新传播到 sync client
# ---------------------------------------------------------------------------


def test_im_config_sync_client_update_token_propagates_to_requests(
    tmp_path: Path,
) -> None:
    """update_token() must refresh _base_headers so subsequent sync_agent calls use the new token.

    feat-394-M3 fix: _IMConfigSyncClient.update_token() is called by the token_getter
    wrapper in main.py after each auto-bind token refresh. Without this, config sync
    holds a stale/empty Bearer token and every sync_agent returns 401.
    """
    workspace_root = tmp_path / "ws-tg"
    workspace_root.mkdir()

    tokens_seen: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        tokens_seen.append(auth)
        if auth != "Bearer refreshed-token-123":
            return httpx.Response(401, json={"detail": "Unauthorized"})
        return httpx.Response(
            200,
            json={
                "agent_id": "tg-agent",
                "display_name": "TG Agent",
                "profile_version": 1,
                "workspace_root": str(workspace_root),
            },
        )

    pipeline = _NullPipeline()
    pipeline.registered = []
    local_config = _make_local_config(tmp_path, workspace_root)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,  # initial token is empty (pre-bind)
        pipeline=pipeline,
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    # Simulate what the token_getter wrapper in main.py does: call update_token()
    # after each successful token refresh so the sync client picks it up.
    sync.update_token("refreshed-token-123")

    sync.sync_agent(agent_id="tg-agent", profile_version=1)

    registered = next(a for a in pipeline.registered if a.agent_id == "tg-agent")
    assert registered.agent_id == "tg-agent"
    # All requests must have used the refreshed token, not the empty initial one.
    assert all(t == "Bearer refreshed-token-123" for t in tokens_seen), (
        f"Expected all requests to use refreshed token, got: {tokens_seen}"
    )


def test_im_config_sync_client_update_token_none_clears_auth(
    tmp_path: Path,
) -> None:
    """update_token(None) must clear the Authorization header from sync requests."""
    workspace_root = tmp_path / "ws-tg-clear"
    workspace_root.mkdir()

    tokens_seen: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        tokens_seen.append(request.headers.get("Authorization", ""))
        return httpx.Response(
            200,
            json={
                "agent_id": "tg-clear",
                "display_name": "TG Clear",
                "profile_version": 1,
                "workspace_root": str(workspace_root),
            },
        )

    pipeline = _NullPipeline()
    pipeline.registered = []
    local_config = _make_local_config(tmp_path, workspace_root)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token="old-token",
        pipeline=pipeline,
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    sync.update_token(None)
    sync.sync_agent(agent_id="tg-clear", profile_version=1)

    # After update_token(None), no Authorization header should be sent.
    assert all(t == "" for t in tokens_seen), (
        f"Expected no auth header after update_token(None), got: {tokens_seen}"
    )
