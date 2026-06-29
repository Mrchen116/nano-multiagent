"""Unit tests for IMConnectionManager: connect, register, heartbeat, retry, send_json, ack."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from personal_assistant.channels.base import InboundMessage
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import NodeConfig
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.reporter.upstream_reporter import UpstreamReporter
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import (
    _FakeWebSocket,
    _FailOnNthSendWebSocket,
    _agents,
    _connect_fake,
    _minimal_reporter,
)


def test_im_connection_connects_registers_and_handles_downstream_frames(
    tmp_path: Path,
) -> None:
    inbound_seen: list[InboundMessage] = []
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(inbound_seen.append)
    sync_client = ConfigSyncClient()
    heartbeat_seen: list[tuple[str, str]] = []
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "relay.message",
                    "payload": {
                        "relay_task_id": "relay-1",
                        "idempotency_key": "idem-1",
                        "message": {
                            "id": "msg-1",
                            "sender_user_id": "user-1",
                            "conversation_id": "conv-1",
                            "content": "hello",
                        },
                        "metadata": {"conversation_type": "direct"},
                    },
                }
            ),
            json.dumps(
                {
                    "type": "config.sync",
                    "payload": {"agent_id": "agent-a", "profile_version": 5},
                }
            ),
            json.dumps(
                {
                    "type": "heartbeat.trigger",
                    "payload": {"agent_id": "agent-a", "reason": "manual"},
                }
            ),
        ]
    )
    connect_calls: list[tuple[str, dict[str, str]]] = []
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000", token="secret"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        sync_client=sync_client,
        heartbeat_trigger=lambda agent_id, reason: heartbeat_seen.append(
            (agent_id, reason)
        ),
        connect=lambda url, headers: _connect_fake(socket, connect_calls, url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        for _ in range(4):
            await manager._listen_once()  # noqa: SLF001 - focused unit coverage for downstream frames

    asyncio.run(_exercise())

    assert manager.connected is True
    sent_register = json.loads(socket.sent[0])
    assert sent_register["type"] == "node.register"
    assert connect_calls == [
        (
            "ws://im.local:9000/im/ws/gateway",
            {"User-Agent": "nano-multiagent-gateway", "Authorization": "Bearer secret"},
        )
    ]
    assert inbound_seen[0].text == "hello"
    assert inbound_seen[0].metadata["message_id"] == "msg-1"
    assert sync_client.latest_profile_version("agent-a") == 5
    assert heartbeat_seen == [("agent-a", "manual")]


def test_im_connection_replies_with_live_agent_config_snapshot(tmp_path: Path) -> None:
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "agent.config.get",
                    "payload": {"request_id": "req-1", "agent_id": "agent-a"},
                }
            ),
        ]
    )
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        agent_config_provider=lambda agent_id: {
            "display_name": "Agent A",
            "system_prompt": "You are local.",
            "skills": ["plan"],
            "tool_allowlist": ["read"],
            "group_reply_policy": "manual",
            "default_model": "claude-sonnet-4",
            "workspace_root": f"/tmp/{agent_id}",
        },
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - ack node.register
        await manager._listen_once()  # noqa: SLF001 - focused unit coverage for downstream request/response
        await manager.close()

    asyncio.run(_exercise())

    response_frame = json.loads(socket.sent[-1])
    assert response_frame == {
        "type": "agent.config",
        "payload": {
            "request_id": "req-1",
            "agent_id": "agent-a",
            "agent": {
                "display_name": "Agent A",
                "system_prompt": "You are local.",
                "skills": ["plan"],
                "tool_allowlist": ["read"],
                "group_reply_policy": "manual",
                "default_model": "claude-sonnet-4",
                "workspace_root": "/tmp/agent-a",
            },
        },
    }


def test_im_connection_dispatches_session_fork_request(tmp_path: Path) -> None:
    """feat-445-M1 R3: a session.fork.request frame is routed to the injected handler,
    and its result is echoed back as session.fork.result with the request_id."""
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "session.fork.request",
                    "payload": {
                        "request_id": "fork-req-1",
                        "source_conversation_id": "conv-src",
                        "new_conversation_id": "conv-new",
                        "agent_id": "agent-a",
                        "fork_point": {"message_id": "a3"},
                    },
                }
            ),
        ]
    )
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    seen: list[dict] = []

    async def fork_handler(payload):
        seen.append(dict(payload))
        return {"ok": True, "new_session_id": "ksess-new"}

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        session_fork_handler=fork_handler,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - ack node.register
        await manager._listen_once()  # noqa: SLF001 - session.fork.request
        await manager.close()

    asyncio.run(_exercise())

    assert seen and seen[0]["fork_point"]["message_id"] == "a3"
    response_frame = json.loads(socket.sent[-1])
    assert response_frame["type"] == "session.fork.result"
    assert response_frame["payload"]["request_id"] == "fork-req-1"
    assert response_frame["payload"]["ok"] is True
    assert response_frame["payload"]["new_session_id"] == "ksess-new"


def test_im_connection_sends_periodic_node_heartbeats_while_connected(
    tmp_path: Path,
) -> None:
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})
        ]
    )
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local:9000", heartbeat_interval_seconds=0.01
        ),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - ack node.register
        await asyncio.sleep(0.03)
        await manager.close()

    asyncio.run(_exercise())

    sent_types = [json.loads(frame)["type"] for frame in socket.sent]
    assert sent_types[:2] == ["node.register", "node.heartbeat"]
    heartbeat_payload = json.loads(socket.sent[1])["payload"]
    assert heartbeat_payload["node_id"] == "node-1"
    assert heartbeat_payload["status"] == "online"
    assert heartbeat_payload["agent_count"] == 1


def test_im_connection_retries_buffered_frame_after_reconnect(tmp_path: Path) -> None:
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    first_socket = _FailOnNthSendWebSocket(fail_on_send_number=2)
    second_socket = _FakeWebSocket()
    sockets = [first_socket, second_socket]
    connect_calls: list[tuple[str, dict[str, str]]] = []

    async def _connect(url: str, headers: dict[str, str]) -> _FakeWebSocket:
        connect_calls.append((url, headers))
        return sockets.pop(0)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=_connect,
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager.send_json("node.report", {"run_id": "run-1", "status": "running"})
        assert manager.connected is False
        assert first_socket.closed == 1
        await manager.connect_once()
        assert first_socket.closed == 1
        assert second_socket.closed == 0

    asyncio.run(_exercise())

    assert connect_calls == [
        ("ws://im.local:9000/im/ws/gateway", {"User-Agent": "nano-multiagent-gateway"}),
        ("ws://im.local:9000/im/ws/gateway", {"User-Agent": "nano-multiagent-gateway"}),
    ]
    assert [json.loads(frame)["type"] for frame in first_socket.sent] == [
        "node.register"
    ]
    assert [json.loads(frame)["type"] for frame in second_socket.sent] == [
        "node.register",
        "node.report",
    ]
    assert json.loads(second_socket.sent[1])["payload"] == {
        "run_id": "run-1",
        "status": "running",
    }


def test_im_connection_retries_unacked_frame_after_disconnect(tmp_path: Path) -> None:
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    first_socket = _FakeWebSocket()
    second_socket = _FakeWebSocket(
        incoming=[
            json.dumps(
                {
                    "type": "ack",
                    "payload": {"message_type": "node.report", "node_id": "node-1"},
                }
            )
        ]
    )
    sockets = [first_socket, second_socket]

    async def _connect(url: str, headers: dict[str, str]) -> _FakeWebSocket:  # noqa: ARG001
        return sockets.pop(0)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=_connect,
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager.send_json(
            "node.report", {"run_id": "run-1", "status": "completed"}
        )
        assert manager._awaiting_ack_type == "node.report"  # noqa: SLF001
        assert [json.loads(frame)["type"] for frame in first_socket.sent] == [
            "node.register",
            "node.report",
        ]
        await manager._disconnect_current_websocket(RuntimeError("socket dropped"))  # noqa: SLF001
        await manager.connect_once()
        assert [json.loads(frame)["type"] for frame in second_socket.sent] == [
            "node.register",
            "node.report",
        ]
        await manager._listen_once()  # noqa: SLF001
        assert manager._awaiting_ack_type is None  # noqa: SLF001
        assert list(manager._pending_frames) == []  # noqa: SLF001

    asyncio.run(_exercise())


def test_im_connection_retries_with_exponential_backoff_until_cap(
    tmp_path: Path,
) -> None:
    attempts = 0
    sleeps: list[float] = []
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)

    async def _connect(url: str, headers: dict[str, str]):  # noqa: ARG001
        nonlocal attempts
        attempts += 1
        raise RuntimeError("offline")

    async def _sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) >= 4:
            manager._stop_requested = True  # noqa: SLF001

    manager = IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local:9000",
            reconnect_initial_seconds=1.0,
            reconnect_max_seconds=5.0,
        ),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=_connect,
        sleep=_sleep,
    )

    asyncio.run(manager.run_forever())

    assert attempts >= 4
    assert sleeps == [1.0, 2.0, 4.0, 5.0]
    assert manager.connected is False


def test_im_connection_send_agent_message_returns_dispatch_ack(tmp_path: Path) -> None:
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "ack",
                    "payload": {
                        "message_type": "agent.message",
                        "conversation_id": "conv-direct-1",
                        "message_id": "msg-1",
                        "target_kind": "user_id",
                        "target_id": "user-1",
                        "source_agent_id": "agent-a",
                    },
                }
            ),
        ]
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - consume node.register ack first
        ack_task = asyncio.create_task(
            manager.send_agent_message({"to": "user-1", "text": "hi"})
        )
        await asyncio.sleep(0)
        await manager._listen_once()  # noqa: SLF001 - consume agent.message ack
        ack = await ack_task
        assert ack.conversation_id == "conv-direct-1"
        assert ack.message_id == "msg-1"
        assert ack.target_kind == "user_id"
        assert ack.target_id == "user-1"
        assert ack.source_agent_id == "agent-a"

    asyncio.run(_exercise())


def test_im_connection_send_json_await_ack_returns_raw_ack_payload(
    tmp_path: Path,
) -> None:
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "ack",
                    "payload": {
                        "message_type": "node.report",
                        "status": "ok",
                        "run_id": "run-1",
                    },
                }
            ),
        ]
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001
        ack_task = asyncio.create_task(
            manager.send_json_await_ack("node.report", {"run_id": "run-1"})
        )
        await asyncio.sleep(0)
        await manager._listen_once()  # noqa: SLF001
        ack = await ack_task
        assert ack == {"message_type": "node.report", "status": "ok", "run_id": "run-1"}

    asyncio.run(_exercise())


def test_im_connection_send_agent_message_fails_when_socket_drops_before_ack(
    tmp_path: Path,
) -> None:
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})
        ]
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        task = asyncio.create_task(
            manager.send_agent_message({"to": "user-1", "text": "hi"})
        )
        await asyncio.sleep(0)
        await manager._disconnect_current_websocket(RuntimeError("socket dropped"))  # noqa: SLF001
        with pytest.raises(RuntimeError, match="before ack"):
            await task
        assert len(manager._pending_frames) == 1  # noqa: SLF001
        assert manager._pending_frames[0].message_type == "agent.message"  # noqa: SLF001

    asyncio.run(_exercise())


# ---------------------------------------------------------------------------
# feat-383-M1 R2: skill_ids + workspace_root transparent pass-through
# ---------------------------------------------------------------------------


def test_im_connection_agent_preview_passes_skill_ids_to_provider(
    tmp_path: Path,
) -> None:
    """agent.prompt.preview.request handler must extract skill_ids and pass them to provider.

    feat-383-M1: provider signature now includes skill_ids so the kernel can
    resolve real skill descriptions.
    """
    provider_calls: list[dict] = []

    async def _fake_provider(
        agent_id,
        workspace_root,
        features,
        custom_prompt,
        tool_ids,
        scenario,
        skill_ids=(),
        heartbeat_enabled=None,  # feat-394-M4 R2-2
        cron_enabled=None,  # feat-394-M4 R2-2
    ):  # type: ignore[misc]
        provider_calls.append(
            {
                "agent_id": agent_id,
                "workspace_root": workspace_root,
                "tool_ids": tool_ids,
                "skill_ids": list(skill_ids),
            }
        )
        return {"prompt": "preview", "section_count": 1}

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "agent.prompt.preview.request",
                    "payload": {
                        "request_id": "req-1",
                        "agent_id": "agent-x",
                        "workspace_root": "/ws/agent-x",
                        "features": {},
                        "custom_prompt": None,
                        "tool_ids": ["read"],
                        "skill_ids": ["plan", "review"],
                        "scenario": "direct",
                    },
                }
            ),
        ]
    )

    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _: None)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="ws://localhost:9999/ws", token="t"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        sync_client=ConfigSyncClient(),
        heartbeat_trigger=lambda _a, _r: None,
        agent_config_provider=None,
        agent_capabilities_provider=None,
        prompt_preview_provider=_fake_provider,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 — consume node.register ack
        await manager._listen_once()  # noqa: SLF001 — process the preview request frame

    asyncio.run(_exercise())

    assert len(provider_calls) == 1, "provider must have been called exactly once"
    call = provider_calls[0]
    assert call["agent_id"] == "agent-x"
    assert call["workspace_root"] == "/ws/agent-x"
    assert call["tool_ids"] == ["read"]
    assert call["skill_ids"] == ["plan", "review"], (
        f"skill_ids must be forwarded to provider, got: {call['skill_ids']}"
    )


def test_im_connection_node_preview_passes_workspace_root_and_skill_ids_to_provider(
    tmp_path: Path,
) -> None:
    """node.prompt.preview.request handler must extract workspace_root + skill_ids and pass them to provider.

    feat-383-M1: node-level preview now carries workspace_root (IM-derived) and
    skill_ids; Gateway handler must forward both to the provider.
    """
    provider_calls: list[dict] = []

    async def _fake_provider(
        agent_id,
        workspace_root,
        features,
        custom_prompt,
        tool_ids,
        scenario,
        skill_ids=(),
    ):  # type: ignore[misc]
        provider_calls.append(
            {
                "agent_id": agent_id,
                "workspace_root": workspace_root,
                "tool_ids": tool_ids,
                "skill_ids": list(skill_ids),
            }
        )
        return {"prompt": "preview-node", "section_count": 1}

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "node.prompt.preview.request",
                    "payload": {
                        "request_id": "req-node-1",
                        "workspace_root": "/ws/new-agent",
                        "features": {},
                        "custom_prompt": None,
                        "tool_ids": ["bash"],
                        "skill_ids": ["code-review"],
                        "scenario": "direct",
                    },
                }
            ),
        ]
    )

    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _: None)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="ws://localhost:9999/ws", token="t"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        sync_client=ConfigSyncClient(),
        heartbeat_trigger=lambda _a, _r: None,
        agent_config_provider=None,
        agent_capabilities_provider=None,
        prompt_preview_provider=_fake_provider,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 — consume node.register ack
        await manager._listen_once()  # noqa: SLF001 — process the node preview request frame

    asyncio.run(_exercise())

    assert len(provider_calls) == 1, "provider must have been called exactly once"
    call = provider_calls[0]
    assert call["workspace_root"] == "/ws/new-agent", (
        f"workspace_root must be forwarded from node preview frame, got: {call['workspace_root']}"
    )
    assert call["skill_ids"] == ["code-review"], (
        f"skill_ids must be forwarded to provider, got: {call['skill_ids']}"
    )


def test_im_connection_does_not_disconnect_on_downstream_error_frame(
    tmp_path: Path,
) -> None:
    """IM 回送 type=error 下行帧（如畸形 node.report 被 IM 拒绝时），Gateway 不应抛 ValueError 触发断线重连。

    根因：_listen_once 对未知 message_type 执行 `raise ValueError`，而 run_forever 的
    `except Exception` 捕获后调用 _mark_disconnected 进入重连循环。正确行为是记录并跳过。

    Migrated from test_gateway_im_connection.py as part of refactor-395-M1 test dedup.
    """
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    socket = _FakeWebSocket(
        incoming=[
            # 1. 注册 ack
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            # 2. IM 对某个帧回送 error（例如对畸形 heartbeat node.report 的拒绝）
            json.dumps(
                {
                    "type": "error",
                    "payload": {
                        "code": "bad_payload",
                        "message": "node_id must be non-empty",
                    },
                }
            ),
            # 3. 正常 relay.message ——证明连接仍然存活
            json.dumps(
                {
                    "type": "relay.message",
                    "payload": {
                        "relay_task_id": "relay-ok",
                        "idempotency_key": "idem-ok",
                        "message": {
                            "id": "msg-ok",
                            "sender_user_id": "user-1",
                            "conversation_id": "conv-1",
                            "content": "still alive",
                        },
                        "metadata": {"conversation_type": "direct"},
                    },
                }
            ),
        ]
    )
    inbound_seen: list = []
    relay_adapter2 = WebRelayAdapter()
    relay_adapter2.start(inbound_seen.append)
    reporter = _minimal_reporter(tmp_path)
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000", token="secret"),
        reporter=reporter,
        relay_adapter=relay_adapter2,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        # node.register → ack
        await manager._listen_once()  # noqa: SLF001
        # error frame ——不应抛 ValueError、不应标记断线
        await manager._listen_once()  # noqa: SLF001
        # relay.message ——连接仍然存活，正常被分发
        await manager._listen_once()  # noqa: SLF001

    asyncio.run(_exercise())

    # 连接未被标记为断开
    assert manager.connected is True
    # 后续 relay.message 正常被分发，说明 error 帧没有打断流程
    assert len(inbound_seen) == 1
    assert inbound_seen[0].text == "still alive"


# ---------------------------------------------------------------------------
# feat-394-M13: gateway-side request frame handlers in im_connection.py
# ---------------------------------------------------------------------------


def test_im_connection_handles_heartbeat_md_request(tmp_path: Path) -> None:
    """node.heartbeat.md.request triggers provider and sends node.heartbeat.md back.

    feat-394-M13 (决策 G): gateway receives the RPC request, reads HEARTBEAT.md
    from its own workspace, and sends a node.heartbeat.md response frame.
    """
    workspace = tmp_path / "agent-ws"
    workspace.mkdir()
    md_content = "# HEARTBEAT\n- Watch server uptime daily"
    (workspace / "HEARTBEAT.md").write_text(md_content)

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "node.heartbeat.md.request",
                    "payload": {
                        "request_id": "req-hbmd-1",
                        "agent_id": "agent-x",
                        "workspace_root": str(workspace),
                    },
                }
            ),
        ]
    )

    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _: None)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="ws://localhost:9999/ws", token="t"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 — ack for node.register
        await manager._listen_once()  # noqa: SLF001 — process heartbeat-md request

    asyncio.run(_exercise())

    sent_frames = [json.loads(f) for f in socket.sent]
    sent_types = [m.get("type") for m in sent_frames]
    assert "node.heartbeat.md" in sent_types, (
        f"Expected node.heartbeat.md frame but got: {sent_types!r}"
    )
    hb_frame = next(m for m in sent_frames if m.get("type") == "node.heartbeat.md")
    assert hb_frame["payload"]["request_id"] == "req-hbmd-1"
    assert hb_frame["payload"]["content"] == md_content


def test_im_connection_heartbeat_md_returns_empty_when_file_missing(
    tmp_path: Path,
) -> None:
    """node.heartbeat.md.request responds with empty content when HEARTBEAT.md absent."""
    workspace = tmp_path / "agent-ws"
    workspace.mkdir()
    # No HEARTBEAT.md created.

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "node.heartbeat.md.request",
                    "payload": {
                        "request_id": "req-hbmd-2",
                        "agent_id": "agent-x",
                        "workspace_root": str(workspace),
                    },
                }
            ),
        ]
    )

    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _: None)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="ws://localhost:9999/ws", token="t"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001
        await manager._listen_once()  # noqa: SLF001

    asyncio.run(_exercise())

    sent_frames = [json.loads(f) for f in socket.sent]
    hb_frame = next(m for m in sent_frames if m.get("type") == "node.heartbeat.md")
    assert hb_frame["payload"]["content"] == ""


def test_im_connection_handles_cron_jobs_request(tmp_path: Path) -> None:
    """node.cron.jobs.request triggers jobs.json read and sends node.cron.jobs back.

    feat-394-M13 (决策 G): gateway reads its own cron/jobs.json and returns the list.
    IM never directly reads workspace files.
    """
    workspace = tmp_path / "agent-ws"
    cron_dir = workspace / ".nanoassistant" / "cron"
    cron_dir.mkdir(parents=True)
    jobs_data = [
        {"id": "job-1", "name": "tick", "schedule": {"kind": "every", "every": "30m"}}
    ]
    (cron_dir / "jobs.json").write_text(
        __import__("json").dumps(jobs_data), encoding="utf-8"
    )

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "node.cron.jobs.request",
                    "payload": {
                        "request_id": "req-cj-1",
                        "agent_id": "agent-x",
                        "workspace_root": str(workspace),
                    },
                }
            ),
        ]
    )

    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _: None)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="ws://localhost:9999/ws", token="t"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001
        await manager._listen_once()  # noqa: SLF001

    asyncio.run(_exercise())

    sent_frames = [json.loads(f) for f in socket.sent]
    sent_types = [m.get("type") for m in sent_frames]
    assert "node.cron.jobs" in sent_types, (
        f"Expected node.cron.jobs frame but got: {sent_types!r}"
    )
    cj_frame = next(m for m in sent_frames if m.get("type") == "node.cron.jobs")
    assert cj_frame["payload"]["request_id"] == "req-cj-1"
    assert cj_frame["payload"]["jobs"] == jobs_data


def test_im_connection_handles_cron_delete_request_job_found(tmp_path: Path) -> None:
    """node.cron.delete.request removes matching job and sends deleted=True."""
    workspace = tmp_path / "agent-ws"
    cron_dir = workspace / ".nanoassistant" / "cron"
    cron_dir.mkdir(parents=True)
    jobs_data = [
        {"id": "job-1", "name": "tick"},
        {"id": "job-2", "name": "check"},
    ]
    import json as _json

    (cron_dir / "jobs.json").write_text(_json.dumps(jobs_data), encoding="utf-8")

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "node.cron.delete.request",
                    "payload": {
                        "request_id": "req-cd-1",
                        "agent_id": "agent-x",
                        "workspace_root": str(workspace),
                        "job_id": "job-1",
                    },
                }
            ),
        ]
    )

    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _: None)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="ws://localhost:9999/ws", token="t"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001
        await manager._listen_once()  # noqa: SLF001

    asyncio.run(_exercise())

    sent_frames = [json.loads(f) for f in socket.sent]
    cd_frame = next(m for m in sent_frames if m.get("type") == "node.cron.delete")
    assert cd_frame["payload"]["request_id"] == "req-cd-1"
    assert cd_frame["payload"]["deleted"] is True

    # Verify the file was actually updated on the gateway side.
    remaining = _json.loads((cron_dir / "jobs.json").read_text())
    assert len(remaining) == 1
    assert remaining[0]["id"] == "job-2"


def test_im_connection_handles_cron_delete_request_job_not_found(
    tmp_path: Path,
) -> None:
    """node.cron.delete.request sends deleted=False when job_id is not in the file."""
    workspace = tmp_path / "agent-ws"
    cron_dir = workspace / ".nanoassistant" / "cron"
    cron_dir.mkdir(parents=True)
    import json as _json

    (cron_dir / "jobs.json").write_text(
        _json.dumps([{"id": "job-other"}]), encoding="utf-8"
    )

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "node.cron.delete.request",
                    "payload": {
                        "request_id": "req-cd-2",
                        "agent_id": "agent-x",
                        "workspace_root": str(workspace),
                        "job_id": "job-missing",
                    },
                }
            ),
        ]
    )

    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _: None)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="ws://localhost:9999/ws", token="t"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001
        await manager._listen_once()  # noqa: SLF001

    asyncio.run(_exercise())

    sent_frames = [json.loads(f) for f in socket.sent]
    cd_frame = next(m for m in sent_frames if m.get("type") == "node.cron.delete")
    assert cd_frame["payload"]["deleted"] is False
