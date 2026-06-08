"""Unit tests for reconcile-on-connect: callback invocation contract.

Tests that _reconcile_on_connect callback is invoked on each successful
connect, skipped on failures, and does not raise on HTTP errors.
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
# 场景 4：对账在 IMConnectionManager.connect_once 完成后触发
# ---------------------------------------------------------------------------


def test_reconcile_callback_invoked_after_connect_once(tmp_path: Path) -> None:
    """connect_once 完成后，reconcile 回调被调用一次。

    验证对账触发时机绑定在 WS bind 完成（node.register ack 收到）之后。
    """
    from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
    from personal_assistant.ws.im_connection import (
        IMConnectionConfig,
        IMConnectionManager,
    )

    from tests.unit.personal_assistant._im_connection_helpers import (
        _FakeWebSocket,
        _connect_fake,
        _minimal_reporter,
    )

    reporter = _minimal_reporter(tmp_path)
    relay_adapter = WebRelayAdapter()
    connect_calls: list[tuple[str, dict[str, str]]] = []
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
        ]
    )

    reconcile_calls: list[None] = []

    async def _reconcile_callback() -> None:
        reconcile_calls.append(None)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, connect_calls, url, headers),
        on_connected=_reconcile_callback,
    )

    asyncio.run(manager.connect_once())

    # connect_once 成功后对账回调被调用
    assert len(reconcile_calls) == 1


# ---------------------------------------------------------------------------
# 场景 5：connect_once 失败时对账回调不被调用
# ---------------------------------------------------------------------------


def test_reconcile_callback_not_invoked_when_connect_fails(tmp_path: Path) -> None:
    """WS 连接失败时，对账回调不应被触发。"""
    from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
    from personal_assistant.ws.im_connection import (
        IMConnectionConfig,
        IMConnectionManager,
    )

    from tests.unit.personal_assistant._im_connection_helpers import _minimal_reporter

    reporter = _minimal_reporter(tmp_path)
    relay_adapter = WebRelayAdapter()

    async def _fail_connect(url: str, headers: Any) -> Any:
        raise ConnectionRefusedError("im not reachable")

    reconcile_calls: list[None] = []

    async def _reconcile_callback() -> None:
        reconcile_calls.append(None)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=_fail_connect,
        on_connected=_reconcile_callback,
    )

    try:
        asyncio.run(manager.connect_once())
    except Exception:
        pass

    # 连接失败 → 对账不触发
    assert len(reconcile_calls) == 0


# ---------------------------------------------------------------------------
# 场景 6：对账 HTTP 失败不中断 WS 连接（记录日志，不 raise）
# ---------------------------------------------------------------------------


def test_reconcile_http_failure_does_not_raise(tmp_path: Path) -> None:
    """对账期间 IM HTTP 请求失败时，异常被记录但不传播，WS 连接保持存活。"""
    pipeline = _FakePipeline()
    local_config = _make_local_config(
        tmp_path,
        [("agent-w", {})],
    )

    def _always_500(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "server error"})

    client = httpx.Client(
        base_url="http://im.local:9000",
        transport=httpx.MockTransport(_always_500),
    )
    sync_client = _IMConfigSyncClient(
        base_url="http://im.local:9000",
        token="tok",
        pipeline=pipeline,
        local_config=local_config,
        client=client,
    )

    # reconcile_all_agents 不应 raise，即使 HTTP 失败
    sync_client.reconcile_all_agents()

    # 失败时没有 register_agent 调用
    assert len(pipeline.registered) == 0


# ---------------------------------------------------------------------------
# 场景 7：connect_once 每次被调用均触发对账（覆盖重连场景语义）
# ---------------------------------------------------------------------------


def test_reconcile_callback_invoked_on_each_connect_once_call(tmp_path: Path) -> None:
    """connect_once 每次成功调用都触发 on_connected 回调，覆盖重连场景语义。

    run_forever 每次重连都会调 connect_once；此测试直接调两次 connect_once 验证
    回调被触发两次，等价于「首次连接 + 断线重连」两个 bind 事件均触发对账。
    """
    from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
    from personal_assistant.ws.im_connection import (
        IMConnectionConfig,
        IMConnectionManager,
    )

    from tests.unit.personal_assistant._im_connection_helpers import (
        _FakeWebSocket,
        _connect_fake,
        _minimal_reporter,
    )

    reporter = _minimal_reporter(tmp_path)
    relay_adapter = WebRelayAdapter()
    connect_calls: list[tuple[str, dict[str, str]]] = []
    reconcile_calls: list[None] = []

    def _make_socket() -> _FakeWebSocket:
        return _FakeWebSocket(
            incoming=[
                json.dumps(
                    {"type": "ack", "payload": {"message_type": "node.register"}}
                ),
            ]
        )

    call_count = 0

    async def _connect_new_socket(url: str, headers: Any) -> _FakeWebSocket:
        nonlocal call_count
        call_count += 1
        socket = _make_socket()
        connect_calls.append((url, dict(headers)))
        return socket

    async def _reconcile_callback() -> None:
        reconcile_calls.append(None)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=_connect_new_socket,
        on_connected=_reconcile_callback,
    )

    async def _two_connects() -> None:
        await manager.connect_once()
        # 模拟断线后重连：强制重置连接状态，再调一次 connect_once
        manager._connected = False  # noqa: SLF001
        manager._websocket = None  # noqa: SLF001
        await manager.connect_once()

    asyncio.run(_two_connects())

    # 两次 connect_once 各触发一次对账
    assert len(reconcile_calls) == 2
