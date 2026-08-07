"""Unit tests for _IMConfigSyncClient: profile polling, session drops, workspace seeding."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import yaml

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    ChannelConfig,
    HeartbeatConfig,
    IMServiceConfig,
    GatewayLifecycleConfig,
    LocalConfig,
    NodeConfig,
    load_local_config,
)
from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.agent_config_sync import (
    IMAgentConfigSync as _IMConfigSyncClient,
    _read_skill_name,
    _make_workspace_root_factory,
)
from personal_assistant.builtin_skills.lark_bundle import lark_skill_names
from tests.unit.personal_assistant._config_sync_test_owners import (
    build_config_sync_test_owners,
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
                LLMModelPayload(name="claude-sonnet-4-6"),
            ),
        ),
    ),
)


def test_read_skill_name_prefers_frontmatter_name(tmp_path: Path) -> None:
    skill_dir = tmp_path / "directory-name"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\nname: declared-name\ndescription: Test skill\n---\n\nBody\n",
        encoding="utf-8",
    )

    assert _read_skill_name(skill_file) == "declared-name"


def test_im_config_sync_client_retries_until_live_agent_config_reaches_target_version(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace-from-im"
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
    config_path = tmp_path / "config.yaml"
    # bugfix-404-M2: workspace_root comes from local config, not IM mirror.
    # agent-live must be in local_config.agents with the expected workspace so
    # sync_agent uses the local-config value instead of the factory default.
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")
            ),
            AgentWorkspaceConfig(agent_id="agent-live", workspace_root=workspace_root),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    owners = build_config_sync_test_owners(local_config)
    initial_revision = owners.catalog.require("agent-live").revision
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=client,
        monotonic=lambda: 0.0,
        sleep=lambda seconds: sleeps.append(seconds),
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    published = owners.catalog.require("agent-live")
    assert published.revision > initial_revision
    assert published.config.workspace_root == workspace_root
    assert sleeps == [0.1, 0.1]
    assert workspace_root.is_dir()
    # feat-349-M3: MEMORY.md/USER.md seed under .nanoassistant/memory/;
    # HEARTBEAT.md stays at workspace root.
    memory_seed = workspace_root / ".nanoassistant" / "memory" / "MEMORY.md"
    assert memory_seed.is_file() is True
    assert (workspace_root / "HEARTBEAT.md").is_file() is True
    assert memory_seed.read_text(encoding="utf-8").strip()
    assert (workspace_root / "HEARTBEAT.md").read_text(encoding="utf-8").strip()


def test_im_config_sync_client_retains_existing_agent_session_bindings_after_profile_refresh(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)

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
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")
            ),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    owners = build_config_sync_test_owners(local_config)
    owners.store.bind(
        session_key="web:conv-1:agent-live",
        kernel_session_id="sess-old",
        reply_context=ReplyContext(channel_name="web_relay", target_chat_id="conv-1"),
    )
    owners.store.bind(
        session_key="web:conv-2:agent-other",
        kernel_session_id="sess-other",
        reply_context=ReplyContext(channel_name="web_relay", target_chat_id="conv-2"),
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        workspace_root_factory=lambda _agent_id: workspace_root,
        client=client,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    assert owners.catalog.require("agent-live").config.workspace_root == workspace_root
    retained = owners.binder.lookup("web:conv-1:agent-live")
    assert retained is not None
    assert retained.kernel_session_id == "sess-old"
    assert owners.binder.lookup("web:conv-2:agent-other") is not None


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
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")
            ),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        workspace_root_factory=lambda _agent_id: workspace_root,
        client=client,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    assert owners.catalog.require("agent-live").config.workspace_root == workspace_root
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
                "custom_prompt": "Current instructions.",
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
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
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
    # bugfix-404-M2: workspace_root comes from local config (factory default for new agents),
    # not from IM mirror.  agent-live is not in local_config.agents, so factory is used.
    assert agent.workspace_root == (
        (Path("~/nano-assistant/workspace") / "agent-live").expanduser().resolve()
    )
    assert agent.skills == ("skill-a", "skill-b")
    assert agent.tool_allowlist == ("Read", "Bash")
    assert agent.custom_prompt == "Current instructions."
    assert "system_prompt" not in sync.current_agent_payload(agent_id="agent-live")
    assert agent.group_reply_policy == "mention_only"
    assert agent.default_model == "claude-sonnet-4-6"


def test_first_mirror_reconcile_persists_authoritative_custom_prompt(
    tmp_path: Path,
) -> None:
    """A successful authoritative mirror read writes the visible prompt field."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = tmp_path / "gateway.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "node": {"node_id": "node-1"},
                "agents": [
                    {
                        "agent_id": "agent-a",
                        "workspace_root": str(workspace),
                        "title": "agent-a",
                        "custom_prompt": None,
                        "skills": [],
                        "tool_allowlist": [],
                        "group_reply_policy": "manual",
                    }
                ],
                "llm": {
                    "default_model": "test:model",
                    "providers": [
                        {
                            "name": "test",
                            "base_url": "http://127.0.0.1:4000",
                            "models": [{"name": "test:model"}],
                        }
                    ],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    local_config = load_local_config(config_path)
    owners = build_config_sync_test_owners(local_config)

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "agent-a",
                "display_name": "agent-a",
                "profile_version": 1,
                "custom_prompt": "Visible role",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "manual",
                "default_model": None,
                "features": {},
            },
        )

    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        max_attempts=1,
    )

    sync.sync_agent(agent_id="agent-a", profile_version=1)

    saved_agent = yaml.safe_load(config_path.read_text(encoding="utf-8"))["agents"][0]
    assert saved_agent["custom_prompt"] == "Visible role"
    assert "system_prompt" not in saved_agent


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
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    return local_config


def test_skill_created_global_enables_explicit_allowlists_and_drops_all_sessions(
    tmp_path: Path,
) -> None:
    global_root = (tmp_path / "global-skills").resolve()
    ws_a = tmp_path / "agent-a"
    ws_b = tmp_path / "agent-b"
    ws_c = tmp_path / "agent-c"
    config_path = tmp_path / "config.yaml"
    requests: list[tuple[str, str, dict[str, object] | None]] = []

    def _profile(agent_id: str, version: int, skills: list[str]) -> dict[str, object]:
        return {
            "agent_id": agent_id,
            "display_name": agent_id,
            "description": "",
            "skills": skills,
            "tool_allowlist": ["skill_manage"],
            "group_reply_policy": "manual",
            "default_model": None,
            "workspace_root": str(tmp_path / agent_id),
            "profile_version": version,
            "features": {},
            "custom_prompt": None,
        }

    versions = {"agent-a": 1, "agent-c": 1}
    skills_by_agent = {"agent-a": ["old-skill"], "agent-c": ["existing-skill"]}

    def _handler(request: httpx.Request) -> httpx.Response:
        body = (
            dict(json.loads(request.content.decode("utf-8")))
            if request.content
            else None
        )
        requests.append((request.method, request.url.path, body))
        agent_id = request.url.path.split("/")[4]
        if request.method == "GET":
            return httpx.Response(
                200,
                json=_profile(agent_id, versions[agent_id], skills_by_agent[agent_id]),
            )
        if request.method == "PATCH":
            assert body is not None
            skills_by_agent[agent_id] = list(body["skills"])
            versions[agent_id] += 1
            return httpx.Response(
                200,
                json=_profile(agent_id, versions[agent_id], skills_by_agent[agent_id]),
            )
        raise AssertionError(f"unexpected request {request.method} {request.url.path}")

    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=ws_a,
                skills=("old-skill",),
            ),
            AgentWorkspaceConfig(agent_id="agent-b", workspace_root=ws_b, skills=()),
            AgentWorkspaceConfig(
                agent_id="agent-c",
                workspace_root=ws_c,
                skills=("existing-skill",),
            ),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    owners = build_config_sync_test_owners(local_config)
    initial_revisions = {
        agent_id: owners.catalog.require(agent_id).revision
        for agent_id in ("agent-a", "agent-b", "agent-c")
    }
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        global_skill_root=global_root,
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    sync.handle_skill_created(
        "agent-a",
        {
            "name": "new-skill",
            "scope": "global",
            "skill_root": str(global_root),
        },
    )

    patch_bodies = [
        body for method, _path, body in requests if method == "PATCH" and body
    ]
    assert [body["skills"] for body in patch_bodies] == [
        ["old-skill", "new-skill"],
        ["existing-skill", "new-skill"],
    ]
    assert all(
        owners.catalog.require(agent_id).revision > initial_revisions[agent_id]
        for agent_id in initial_revisions
    )


def test_skill_created_agent_scope_only_enables_executing_agent(
    tmp_path: Path,
) -> None:
    ws_a = tmp_path / "agent-a"
    ws_b = tmp_path / "agent-b"
    agent_root = (ws_a / ".nanoassistant" / "skills").resolve()
    requests: list[tuple[str, str, dict[str, object] | None]] = []
    version = 1
    skills = ["old-skill"]

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal version, skills
        body = (
            dict(json.loads(request.content.decode("utf-8")))
            if request.content
            else None
        )
        requests.append((request.method, request.url.path, body))
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "agent_id": "agent-a",
                    "display_name": "agent-a",
                    "description": "",
                    "skills": skills,
                    "tool_allowlist": [],
                    "group_reply_policy": "manual",
                    "default_model": None,
                    "workspace_root": str(ws_a),
                    "profile_version": version,
                    "features": {},
                    "custom_prompt": None,
                },
            )
        if request.method == "PATCH":
            assert body is not None
            skills = list(body["skills"])
            version += 1
            return httpx.Response(
                200,
                json={**body, "agent_id": "agent-a", "profile_version": version},
            )
        raise AssertionError(f"unexpected request {request.method} {request.url.path}")

    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=ws_a,
                skills=("old-skill",),
            ),
            AgentWorkspaceConfig(
                agent_id="agent-b",
                workspace_root=ws_b,
                skills=("old-skill",),
            ),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "config.yaml",
    )
    owners = build_config_sync_test_owners(local_config)
    agent_b_revision = owners.catalog.require("agent-b").revision
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    sync.handle_skill_created(
        "agent-a",
        {
            "name": "agent-skill",
            "scope": "agent",
            "skill_root": str(agent_root),
        },
    )

    patch_bodies = [
        body for method, _path, body in requests if method == "PATCH" and body
    ]
    assert [body["skills"] for body in patch_bodies] == [["old-skill", "agent-skill"]]
    assert owners.catalog.require("agent-a").config.skills == (
        "old-skill",
        "agent-skill",
    )
    assert owners.catalog.require("agent-b").revision == agent_b_revision


def test_ensure_agent_skills_enabled_updates_explicit_local_allowlist_once(
    tmp_path: Path,
) -> None:
    """A managed Feishu runtime enables its declared skill through the public API."""
    workspace_root = tmp_path / "agent-a"
    skills = ["existing-skill"]
    version = 1
    patch_count = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal patch_count, version, skills
        body = (
            dict(json.loads(request.content.decode("utf-8")))
            if request.content
            else None
        )
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "agent_id": "agent-a",
                    "display_name": "Agent A",
                    "description": "",
                    "skills": skills,
                    "tool_allowlist": [],
                    "group_reply_policy": "manual",
                    "default_model": None,
                    "workspace_root": str(workspace_root),
                    "profile_version": version,
                    "features": {},
                    "custom_prompt": None,
                },
            )
        assert request.method == "PATCH"
        patch_count += 1
        assert body is not None
        skills = list(body["skills"])
        version += 1
        return httpx.Response(
            200,
            json={**body, "agent_id": "agent-a", "profile_version": version},
        )

    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=workspace_root,
                skills=("existing-skill",),
            ),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "config.yaml",
    )
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    assert sync.ensure_agent_skills_enabled("agent-a", lark_skill_names()) is True
    assert sync.ensure_agent_skills_enabled("agent-a", lark_skill_names()) is True
    assert owners.catalog.require("agent-a").config.skills == (
        "existing-skill",
        *lark_skill_names(),
    )
    assert patch_count == 1
    assert sync.ensure_agent_skills_enabled("missing", lark_skill_names()) is False


def test_ensure_agent_skills_enabled_keeps_empty_allowlist_unmaterialized(
    tmp_path: Path,
) -> None:
    """Managed agents with an empty list retain global discovery semantics."""
    workspace_root = tmp_path / "agent-open"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-open"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-open",
                workspace_root=workspace_root,
                skills=(),
            ),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "config.yaml",
    )
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: (_ for _ in ()).throw(AssertionError("no HTTP"))
            ),
            base_url="http://im.local",
            trust_env=False,
        ),
    )

    assert sync.ensure_agent_skills_enabled("agent-open", lark_skill_names()) is True
    assert owners.catalog.require("agent-open").config.skills == ()


def test_sync_agent_repairs_static_feishu_mirror_once_before_publish(
    tmp_path: Path,
) -> None:
    """A config.sync mirror cannot replace a static binding's required bundle."""
    workspace_root = tmp_path / "agent-static"
    skills = ["memory"]
    profile_version = 1
    patch_count = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal patch_count, profile_version, skills
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "agent_id": "agent-static",
                    "display_name": "Static",
                    "profile_version": profile_version,
                    "skills": skills,
                    "workspace_root": str(workspace_root),
                },
            )
        patch_count += 1
        body = dict(json.loads(request.content.decode("utf-8")))
        skills = list(body["skills"])
        profile_version += 1
        return httpx.Response(
            200,
            json={
                **body,
                "agent_id": "agent-static",
                "profile_version": profile_version,
            },
        )

    local_config = LocalConfig(
        node=NodeConfig(node_id="node-static"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent-static",
                workspace_root=workspace_root,
                skills=("memory",),
            ),
        ),
        channels=(
            ChannelConfig(
                name="feishu:agent-static",
                settings={"appId": "cli_static", "appSecret": "secret"},
            ),
        ),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "config.yaml",
    )
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    sync.sync_agent(agent_id="agent-static", profile_version=1)
    sync.sync_agent(agent_id="agent-static", profile_version=profile_version)

    expected = ("memory", *lark_skill_names())
    assert patch_count == 1
    assert tuple(skills) == expected
    assert owners.catalog.require("agent-static").config.skills == expected
    assert sync.current_agent_payload(agent_id="agent-static") == {
        "display_name": "Static",
        "skills": [*expected],
        "tool_allowlist": [],
        "group_reply_policy": "manual",
        "default_model": None,
        "reasoning_effort": None,
        "workspace_root": str(workspace_root),
        "features": {},
        "custom_prompt": None,
        "heartbeat_json": None,
    }


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

    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
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

    registered = owners.catalog.require("alpha").config
    # features must be passed through from IM payload
    assert registered.features.get("memory_curation") is False
    assert registered.custom_prompt == "You are a legal advisor."


def test_handle_agent_create_passes_through_features(tmp_path: Path) -> None:
    """handle_agent_create must include features + custom_prompt in the created AgentWorkspaceConfig."""
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()

    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
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
    registered = owners.catalog.require("beta").config
    assert registered.features.get("skill_creation") is False
    assert registered.custom_prompt == "You are a chef."


def test_handle_agent_create_defaults_to_pa_global_skills(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    skill_dir = home / ".nanoassistant" / "skills" / "global-helper"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: global-helper\ndescription: global helper\n---\n",
        encoding="utf-8",
    )
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
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
        {"agent_id": "beta", "workspace_root": str(workspace_root)}
    )

    assert result["skills"] == ["global-helper"]
    registered = owners.catalog.require("beta").config
    assert registered.skills == ("global-helper",)


def test_handle_agent_create_respects_explicit_empty_skills(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    skill_dir = home / ".nanoassistant" / "skills" / "global-helper"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: global-helper\ndescription: global helper\n---\n",
        encoding="utf-8",
    )
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
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
        {"agent_id": "beta", "workspace_root": str(workspace_root), "skills": []}
    )

    assert result["skills"] == []
    registered = owners.catalog.require("beta").config
    assert registered.skills == ()


def test_handle_agent_create_persists_default_model_to_source_path(
    tmp_path: Path,
) -> None:
    """bugfix-429 R4 (链路B): a dynamically-created agent's default_model is written
    to the loaded config path so it survives a Gateway restart.

    Locks the persistence the original incident reported missing — reload from
    source_path must carry the agent and its selected model.
    """
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    # Seed agent's workspace must exist on disk so the reload below validates.
    (tmp_path / "seed").mkdir()
    # Config must declare the gpt model (openai_compat) so reload validation
    # accepts it — mirrors the cross-provider case the incident reported.
    llm_with_gpt = LLMConfigPayload(
        default_model="kimiCoding:K2.6",
        providers=(
            LLMProviderPayload(
                name="anthropic",
                base_url="http://127.0.0.1:4000",
                models=(LLMModelPayload(name="kimiCoding:K2.6"),),
            ),
            LLMProviderPayload(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(LLMModelPayload(name="codex_oauth:gpt-5.5"),),
            ),
        ),
    )
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-r4"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed", workspace_root=tmp_path / "seed"),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=llm_with_gpt,
        source_path=tmp_path / "config.yaml",
    )
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={})),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    sync.handle_agent_create(
        {
            "agent_id": "gpt-probe",
            "workspace_root": str(workspace_root),
            "default_model": "codex_oauth:gpt-5.5",
        }
    )

    # Reload from disk: the dynamic agent + its model must be there (restart-safe).
    persisted = load_local_config(local_config.source_path)
    agent = next(a for a in persisted.agents if a.agent_id == "gpt-probe")
    assert agent.default_model == "codex_oauth:gpt-5.5"


def test_handle_agent_create_persists_to_default_config_path(tmp_path: Path) -> None:
    """bugfix-429 R4 (链路B, 默认路径场景): when the Gateway is started WITHOUT
    ``--config`` (default ``~/.nano-assistant/config.yaml``), a dynamically-created
    agent's default_model must still be written to that default path.

    Mirrors the operator's first-hand reproduction: ``source_path`` resolves to the
    default config (not None), and the write lands there. Live-verified under an
    isolated HOME; this locks it as a regression independent of ``--config``.
    """
    # default_local_config_path() resolves to a tmp file we own (no HOME pollution).
    default_cfg = tmp_path / ".nano-assistant" / "config.yaml"
    default_cfg.parent.mkdir(parents=True)
    (tmp_path / "seed").mkdir()
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()

    llm_with_gpt = LLMConfigPayload(
        default_model="kimiCoding:K2.6",
        providers=(
            LLMProviderPayload(
                name="anthropic",
                base_url="http://127.0.0.1:4000",
                models=(LLMModelPayload(name="kimiCoding:K2.6"),),
            ),
            LLMProviderPayload(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(LLMModelPayload(name="codex_oauth:gpt-5.5"),),
            ),
        ),
    )
    # source_path = the default path, exactly as main resolves it when --config is absent.
    local_config = LocalConfig(
        node=NodeConfig(node_id="repro-default-node"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed", workspace_root=tmp_path / "seed"),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=llm_with_gpt,
        source_path=default_cfg,
    )
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={})),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    sync.handle_agent_create(
        {
            "agent_id": "gpt-probe",
            "workspace_root": str(workspace_root),
            "default_model": "codex_oauth:gpt-5.5",
        }
    )

    # The default-path config file must now carry the dynamic agent + its model.
    assert default_cfg.exists()
    persisted = load_local_config(default_cfg)
    agent = next(a for a in persisted.agents if a.agent_id == "gpt-probe")
    assert agent.default_model == "codex_oauth:gpt-5.5"


# ---------------------------------------------------------------------------
# bugfix-424 (#127): dynamically-created agents derive workspace from config base
# ---------------------------------------------------------------------------


def test_make_workspace_root_factory_none_when_base_unset() -> None:
    """No workspace_base → factory is None so the caller keeps its legacy default."""
    assert _make_workspace_root_factory(None) is None
    assert _make_workspace_root_factory("") is None
    assert _make_workspace_root_factory("   ") is None


def test_make_workspace_root_factory_roots_under_base(tmp_path: Path) -> None:
    """workspace_base set → factory maps agent_id to <base>/<agent_id>."""
    factory = _make_workspace_root_factory(str(tmp_path / "iso"))
    assert factory is not None
    assert factory("alpha") == tmp_path / "iso" / "alpha"


def test_handle_agent_create_derives_workspace_from_injected_base(
    tmp_path: Path,
) -> None:
    """bugfix-424 (#127): an agent created without an explicit workspace_root lands
    under the injected factory base — not the hardcoded ~/nano-assistant/workspace."""
    base = tmp_path / "iso-base"
    local_config = _make_local_config(tmp_path, tmp_path / "preset-ws")
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={})),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
        workspace_root_factory=_make_workspace_root_factory(str(base)),
    )

    # No workspace_root in the payload → must fall to the injected factory.
    result = sync.handle_agent_create({"agent_id": "dyn"})

    expected = (base / "dyn").resolve()
    assert result["workspace_root"] == str(expected)
    registered = owners.catalog.require("dyn").config
    assert registered.workspace_root == expected
    # The hardcoded home default must NOT be used.
    assert "nano-assistant/workspace" not in result["workspace_root"]


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
                # M9-E: enable comes from features, cadence from heartbeat dict
                "features": {"heartbeat": True},
                "heartbeat": {"every": "10m"},
            },
        )

    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
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

    registered = owners.catalog.require("hb-agent").config
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

    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
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

    registered = owners.catalog.require("no-hb-agent").config
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
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
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

    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,  # initial token is empty (pre-bind)
        **owners.kwargs(),
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

    registered = owners.catalog.require("tg-agent").config
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

    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token="old-token",
        **owners.kwargs(),
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


# ---------------------------------------------------------------------------
# bugfix-404-M2 R2: sync_agent 不采用 IM mirror workspace_root
# ---------------------------------------------------------------------------


def test_sync_agent_ignores_mirror_workspace_root_and_uses_local_config(
    tmp_path: Path,
) -> None:
    """sync_agent 必须使用本地 config 的 workspace_root，IM 给的脏值不得污染 runtime。

    bugfix-404-M2 决策 4：workspace_root 唯一来源是本地 config；IM mirror 值用于展示，
    不进 runtime。哪怕 IM 持有旧的/错误的路径（存量脏 DB），runtime 也不受影响。
    """
    local_ws = tmp_path / "correct-local-workspace"
    dirty_im_ws = tmp_path / "dirty-im-workspace"

    response = httpx.Response(
        200,
        json={
            "agent_id": "Arch",
            "display_name": "Arch",
            "profile_version": 1,
            # IM mirror 携带脏值（主仓 managed default），与本地 config 不一致
            "workspace_root": str(dirty_im_ws),
        },
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        return response

    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://im.local",
        trust_env=False,
    )
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(AgentWorkspaceConfig(agent_id="Arch", workspace_root=local_ws),),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=config_path,
    )
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=client,
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )
    sync.sync_agent(agent_id="Arch", profile_version=1)

    registered = owners.catalog.require("Arch").config
    assert registered.workspace_root == local_ws, (
        f"sync_agent 应使用本地 config workspace {local_ws!r}，"
        f"实际注册了 {registered.workspace_root!r}"
        f"（IM 脏值 {dirty_im_ws!r} 不应渗入 runtime）"
    )
