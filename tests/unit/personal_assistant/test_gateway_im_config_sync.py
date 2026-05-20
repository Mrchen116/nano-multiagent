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


def test_im_config_sync_client_retries_until_live_agent_config_reaches_target_version(tmp_path: Path) -> None:
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

    client = httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://im.local", trust_env=False)
    pipeline = _Pipeline()
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
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


def test_im_config_sync_client_drops_existing_agent_session_bindings_after_profile_refresh(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)

    class _Pipeline:
        def __init__(self) -> None:
            self.registered: list[tuple[str, str]] = []
            self._session_store = SessionBindingStore()
            self._session_store.bind(
                session_key="web:conv-1:agent-live",
                kernel_session_id="sess-old",
                reply_context=type("_ReplyContext", (), {"channel_name": "web_relay", "target_chat_id": "conv-1", "thread_id": None, "metadata": {}})(),
            )
            self._session_store.bind(
                session_key="web:conv-2:agent-other",
                kernel_session_id="sess-other",
                reply_context=type("_ReplyContext", (), {"channel_name": "web_relay", "target_chat_id": "conv-2", "thread_id": None, "metadata": {}})(),
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
            json={"agent_id": "agent-live", "display_name": "Agent Live", "profile_version": 2},
        )

    pipeline = _Pipeline()
    client = httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://im.local", trust_env=False)
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
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


def test_im_config_sync_client_does_not_overwrite_existing_workspace_files(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    # feat-349-M3: MEMORY.md seeds under .nanoassistant/memory/; HEARTBEAT.md at root.
    memory_path = workspace_root / ".nanoassistant" / "memory" / "MEMORY.md"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_path = workspace_root / "HEARTBEAT.md"
    memory_path.write_text("existing memory\n", encoding="utf-8")
    heartbeat_path.write_text("interval: 1h\n\n- Existing heartbeat\n", encoding="utf-8")
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
            json={"agent_id": "agent-live", "display_name": "Agent Live", "profile_version": 2},
        )

    client = httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://im.local", trust_env=False)
    pipeline = _Pipeline()
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
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
    assert heartbeat_path.read_text(encoding="utf-8") == "interval: 1h\n\n- Existing heartbeat\n"


def test_im_config_sync_client_persists_agent_config_to_source_path(tmp_path: Path) -> None:
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
        source_path=config_path,
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=_Pipeline(),
        local_config=local_config,
        client=httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://im.local", trust_env=False),
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
