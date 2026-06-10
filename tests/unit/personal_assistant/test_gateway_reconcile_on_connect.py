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
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.main import _IMConfigSyncClient

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


class _FakePipeline:
    """记录 register_agent 调用，供断言使用。"""

    def __init__(self) -> None:
        self.registered: list[AgentWorkspaceConfig] = []
        self.dropped: list[str] = []

    def register_agent(self, agent: AgentWorkspaceConfig) -> None:
        self.registered.append(agent)

    def drop_agent_sessions(self, agent_id: str) -> None:
        self.dropped.append(agent_id)


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
        kernel=KernelConfig(),
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
    pipeline = _FakePipeline()
    # gateway 内存中 agent 的 heartbeat feature 是 True（旧值）
    local_config = _make_local_config(
        tmp_path,
        [("agent-x", {"features": {"heartbeat": True}})],
    )

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
        pipeline=pipeline,
        local_config=local_config,
        client=client,
    )

    # 对账前 pipeline 没有被调用
    assert len(pipeline.registered) == 0

    # 触发对账
    sync_client.reconcile_all_agents()

    # 对账后 register_agent 被调用，且 heartbeat 已收敛到 False
    assert len(pipeline.registered) == 1
    registered = pipeline.registered[0]
    assert registered.agent_id == "agent-x"
    assert registered.features.get("heartbeat") is False


# ---------------------------------------------------------------------------
# 场景 2：对账拉到较旧 profile_version（< 内存版本），保留内存状态（取大）
# ---------------------------------------------------------------------------


def test_reconcile_skips_update_when_im_profile_version_is_older(
    tmp_path: Path,
) -> None:
    """对账拉到比内存 profile_version 更旧的版本时，不覆盖内存（取大原则）。

    IM mirror 可能返回旧版本（缓存延迟）；增量推送已带来更新版本时对账不应回退。
    """
    pipeline = _FakePipeline()
    local_config = _make_local_config(
        tmp_path,
        [("agent-y", {"features": {"heartbeat": True}})],
    )
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
        pipeline=pipeline,
        local_config=local_config,
        client=client,
    )

    # memory_versions 告知对账：agent-y 当前内存版本是 5
    sync_client.reconcile_all_agents(memory_versions={"agent-y": 5})

    # IM 版本 2 < 内存版本 5 → 不覆盖
    assert len(pipeline.registered) == 0


# ---------------------------------------------------------------------------
# 场景 3：对账拉到相同或更新 profile_version，正常覆盖内存
# ---------------------------------------------------------------------------


def test_reconcile_updates_when_im_profile_version_is_equal_or_newer(
    tmp_path: Path,
) -> None:
    """对账拉到 profile_version >= 内存版本时，覆盖内存 config。"""
    pipeline = _FakePipeline()
    local_config = _make_local_config(
        tmp_path,
        [("agent-z", {"features": {"heartbeat": True}})],
    )
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
        pipeline=pipeline,
        local_config=local_config,
        client=client,
    )

    sync_client.reconcile_all_agents(memory_versions={"agent-z": 3})

    # IM 版本 3 >= 内存版本 3 → 覆盖
    assert len(pipeline.registered) == 1
    registered = pipeline.registered[0]
    assert registered.features.get("heartbeat") is False
    assert registered.features.get("cron_scheduling") is True
