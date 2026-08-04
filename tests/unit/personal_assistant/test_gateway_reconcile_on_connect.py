"""Unit tests for reconcile-on-connect: gateway 在 WS bind 完成后对所有 agent 做全量配置对账。

决策 F (feat-394-M12)：gateway 连上（含重连）IM 完成 bind 后，对该 node 下所有 agent
拉一次 IM 权威 profile（source=mirror）做全量对账，register_agent 覆盖本地内存 config，
使 enabled/features/cadence/active_hours 收敛到 IM 真值；与增量推送并存时按 profile_version 取大。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, call

import httpx

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
from personal_assistant.gateway.agent_config_sync import (
    IMAgentConfigSync as _IMConfigSyncClient,
)
from personal_assistant.builtin_skills.lark_bundle import lark_skill_names
from tests.unit.personal_assistant._config_sync_test_owners import (
    build_config_sync_test_owners,
)


from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

_DEFAULT_LLM = LLMConfigPayload(
    default_model="test-model",
    providers=(
        LLMProviderPayload(
            name="anthropic",
            base_url="http://127.0.0.1:4000",
            models=(LLMModelPayload(name="test-model"),),
        ),
    ),
)


def _make_local_config(
    tmp_path: Path,
    agents: list[tuple[str, dict[str, Any]]],
) -> LocalConfig:
    """构造含指定 agents 的 LocalConfig，workspace_root 指向 tmp_path。"""
    agent_configs = []
    for agent_id, extra in agents:
        ws = tmp_path / agent_id
        ws.mkdir(exist_ok=True)
        kwargs: dict[str, Any] = {
            "agent_id": agent_id,
            "workspace_root": ws,
        }
        kwargs.update(extra)
        agent_configs.append(AgentWorkspaceConfig(**kwargs))
    return LocalConfig(
        node=NodeConfig(node_id="test-node"),
        agents=tuple(agent_configs),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local:9000", token="tok"),
        llm=_DEFAULT_LLM,
        source_path=tmp_path / "config.yaml",
    )


# ---------------------------------------------------------------------------
# 场景 1：对账拉到 enabled=False，覆盖内存中 enabled=True（漏一次增量推送场景）
# ---------------------------------------------------------------------------


def test_reconcile_updates_disabled_heartbeat_when_missed_incremental_push(
    tmp_path: Path,
) -> None:
    """模拟 gateway 离线期间 IM 把 heartbeat 关掉，重连后对账把内存状态收敛到 False。

    这是 bug C 的核心场景：如果没有对账，gateway 一直认为 heartbeat=True 继续打。
    """
    # gateway 内存中 agent 的 heartbeat feature 是 True（旧值）
    local_config = _make_local_config(
        tmp_path,
        [("agent-x", {"features": {"heartbeat": True}})],
    )
    owners = build_config_sync_test_owners(local_config)

    ws = tmp_path / "agent-x"

    responses = iter(
        [
            httpx.Response(
                200,
                json={
                    "agent_id": "agent-x",
                    "display_name": "Agent X",
                    "profile_version": 5,
                    "workspace_root": str(ws),
                    # IM 真值：heartbeat 已关闭
                    "features": {"heartbeat": False},
                },
            )
        ]
    )

    client = httpx.Client(
        base_url="http://im.local:9000",
        transport=httpx.MockTransport(lambda req: next(responses)),
    )
    sync_client = _IMConfigSyncClient(
        base_url="http://im.local:9000",
        token="tok",
        **owners.kwargs(),
        local_config=local_config,
        client=client,
    )

    initial_revision = owners.catalog.require("agent-x").revision

    # 触发对账
    sync_client.reconcile_all_agents()

    registered_snapshot = owners.catalog.require("agent-x")
    assert registered_snapshot.revision > initial_revision
    registered = registered_snapshot.config
    assert registered.agent_id == "agent-x"
    assert registered.features.get("heartbeat") is False
    persisted = load_local_config(local_config.source_path)
    assert persisted.agents[0].features.get("heartbeat") is False


def test_reconcile_persists_enabled_skills_for_live_config_after_restart(
    tmp_path: Path,
) -> None:
    """Reconnect reconcile must update the config backing ``agent.config.get``.

    Without the persist step, ``pipeline._agents`` used the IM mirror skills but
    ``current_agent_payload()`` still reported the stale local empty skills list.
    """

    local_config = _make_local_config(tmp_path, [("agent-skills", {"skills": ()})])
    owners = build_config_sync_test_owners(local_config)
    ws = tmp_path / "agent-skills"
    responses = iter(
        [
            httpx.Response(
                200,
                json={
                    "agent_id": "agent-skills",
                    "display_name": "Agent Skills",
                    "profile_version": 7,
                    "workspace_root": str(ws),
                    "skills": [
                        "skill-creator",
                        "systematic-debugging",
                        "tdd-execution-worker",
                    ],
                },
            )
        ]
    )
    client = httpx.Client(
        base_url="http://im.local:9000",
        transport=httpx.MockTransport(lambda req: next(responses)),
    )
    sync_client = _IMConfigSyncClient(
        base_url="http://im.local:9000",
        token="tok",
        **owners.kwargs(),
        local_config=local_config,
        client=client,
    )

    sync_client.reconcile_all_agents()

    expected = (
        "skill-creator",
        "systematic-debugging",
        "tdd-execution-worker",
    )
    assert owners.catalog.require("agent-skills").config.skills == expected
    assert sync_client.current_agent_payload(agent_id="agent-skills")["skills"] == [
        *expected
    ]
    persisted = load_local_config(local_config.source_path)
    assert persisted.agents[0].skills == expected


# ---------------------------------------------------------------------------
# 场景 2：对账拉到较旧 profile_version（< 内存版本），保留内存状态（取大）
# ---------------------------------------------------------------------------


def test_reconcile_skips_update_when_im_profile_version_is_older(
    tmp_path: Path,
) -> None:
    """对账拉到比内存 profile_version 更旧的版本时，不覆盖内存（取大原则）。

    IM mirror 可能返回旧版本（缓存延迟）；增量推送已带来更新版本时对账不应回退。
    """
    local_config = _make_local_config(
        tmp_path,
        [("agent-y", {"features": {"heartbeat": True}})],
    )
    owners = build_config_sync_test_owners(local_config)
    # 内存中已知 agent-y 的 profile_version（通过增量推送写入）
    # reconcile 应在知道内存版本时才跳过；此场景用 reconcile_all_agents 接受 memory_versions 参数
    ws = tmp_path / "agent-y"

    responses = iter(
        [
            httpx.Response(
                200,
                json={
                    "agent_id": "agent-y",
                    "display_name": "Agent Y",
                    # IM 返回版本 2，而内存已是版本 5（增量推送带来的）
                    "profile_version": 2,
                    "workspace_root": str(ws),
                    "features": {"heartbeat": False},
                },
            )
        ]
    )
    client = httpx.Client(
        base_url="http://im.local:9000",
        transport=httpx.MockTransport(lambda req: next(responses)),
    )
    sync_client = _IMConfigSyncClient(
        base_url="http://im.local:9000",
        token="tok",
        **owners.kwargs(),
        local_config=local_config,
        client=client,
    )

    # memory_versions 告知对账：agent-y 当前内存版本是 5
    sync_client.reconcile_all_agents(memory_versions={"agent-y": 5})

    # IM 版本 2 < 内存版本 5 → 不覆盖
    assert owners.catalog.require("agent-y").revision == 1


# ---------------------------------------------------------------------------
# 场景 3：对账拉到相同或更新 profile_version，正常覆盖内存
# ---------------------------------------------------------------------------


def test_reconcile_updates_when_im_profile_version_is_equal_or_newer(
    tmp_path: Path,
) -> None:
    """对账拉到 profile_version >= 内存版本时，覆盖内存 config。"""
    local_config = _make_local_config(
        tmp_path,
        [("agent-z", {"features": {"heartbeat": True}})],
    )
    owners = build_config_sync_test_owners(local_config)
    ws = tmp_path / "agent-z"

    responses = iter(
        [
            httpx.Response(
                200,
                json={
                    "agent_id": "agent-z",
                    "display_name": "Agent Z",
                    # IM 版本 3 >= 内存版本 3
                    "profile_version": 3,
                    "workspace_root": str(ws),
                    "features": {"heartbeat": False, "cron_scheduling": True},
                },
            )
        ]
    )
    client = httpx.Client(
        base_url="http://im.local:9000",
        transport=httpx.MockTransport(lambda req: next(responses)),
    )
    sync_client = _IMConfigSyncClient(
        base_url="http://im.local:9000",
        token="tok",
        **owners.kwargs(),
        local_config=local_config,
        client=client,
    )

    sync_client.reconcile_all_agents(memory_versions={"agent-z": 3})

    # IM 版本 3 >= 内存版本 3 → 覆盖
    registered = owners.catalog.require("agent-z").config
    assert registered.features.get("heartbeat") is False
    assert registered.features.get("cron_scheduling") is True


def test_reconcile_ignores_mirror_workspace_root_and_uses_local_config(
    tmp_path: Path,
) -> None:
    """reconcile_all_agents must not let IM mirror workspace override local runtime."""
    local_config = _make_local_config(
        tmp_path,
        [("agent-local", {"features": {"heartbeat": True}})],
    )
    owners = build_config_sync_test_owners(local_config)
    local_ws = local_config.agents[0].workspace_root
    dirty_im_ws = tmp_path / "dirty-im-mirror"

    responses = iter(
        [
            httpx.Response(
                200,
                json={
                    "agent_id": "agent-local",
                    "display_name": "Agent Local",
                    "profile_version": 8,
                    "workspace_root": str(dirty_im_ws),
                    "features": {"heartbeat": False, "cron_scheduling": True},
                },
            )
        ]
    )
    client = httpx.Client(
        base_url="http://im.local:9000",
        transport=httpx.MockTransport(lambda req: next(responses)),
    )
    sync_client = _IMConfigSyncClient(
        base_url="http://im.local:9000",
        token="tok",
        **owners.kwargs(),
        local_config=local_config,
        client=client,
        workspace_root_factory=lambda agent_id: tmp_path / "factory" / agent_id,
    )

    sync_client.reconcile_all_agents(memory_versions={"agent-local": 7})

    registered = owners.catalog.require("agent-local").config
    assert registered.workspace_root == local_ws
    assert (local_ws / "HEARTBEAT.md").is_file()
    assert not dirty_im_ws.exists()


def test_reconcile_repairs_static_feishu_mirror_once_before_publish(
    tmp_path: Path,
) -> None:
    """Reconnect keeps a static Feishu agent's explicit bundle complete."""
    workspace_root = tmp_path / "agent-static"
    skills = ["memory"]
    version = 1
    patch_count = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal patch_count, skills, version
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "agent_id": "agent-static",
                    "display_name": "Static",
                    "profile_version": version,
                    "skills": skills,
                    "workspace_root": str(workspace_root),
                },
            )
        patch_count += 1
        body = dict(json.loads(request.content.decode("utf-8")))
        skills = list(body["skills"])
        version += 1
        return httpx.Response(
            200,
            json={
                **body,
                "agent_id": "agent-static",
                "profile_version": version,
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
        im_service=IMServiceConfig(url="http://im.local:9000", token="tok"),
        llm=_DEFAULT_LLM,
        source_path=tmp_path / "config.yaml",
    )
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local:9000",
        token="tok",
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local:9000",
        ),
    )

    sync.reconcile_all_agents()
    sync.reconcile_all_agents()

    expected = ("memory", *lark_skill_names())
    assert patch_count == 1
    assert tuple(skills) == expected
    assert owners.catalog.require("agent-static").config.skills == expected
    assert load_local_config(local_config.source_path).agents[0].skills == expected
