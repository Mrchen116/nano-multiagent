"""IM connection manager and config sync client tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import AgentWorkspaceConfig, NodeConfig
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.reporter.upstream_reporter import UpstreamReporter
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager


class _FakeWebSocket:
    def __init__(self, incoming: list[str] | None = None) -> None:
        self.incoming = list(incoming or [])
        self.sent: list[str] = []
        self.closed = 0

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        if not self.incoming:
            raise RuntimeError("socket closed")
        return self.incoming.pop(0)

    async def close(self) -> None:
        self.closed += 1


class _FailOnNthSendWebSocket(_FakeWebSocket):
    def __init__(self, *, fail_on_send_number: int, incoming: list[str] | None = None) -> None:
        super().__init__(incoming=incoming)
        self._fail_on_send_number = fail_on_send_number
        self._send_count = 0

    async def send(self, data: str) -> None:
        self._send_count += 1
        if self._send_count == self._fail_on_send_number:
            raise RuntimeError("socket closed")
        await super().send(data)


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    return (
        AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=workspace,
            title="Agent A",
            skills=("plan", "playwright"),
            tool_allowlist=("read", "bash"),
            default_model="codex_oauth:gpt-5.5",
        ),
    )


async def _connect_fake(
    socket: _FakeWebSocket,
    connect_calls: list[tuple[str, dict[str, str]]],
    url: str,
    headers: dict[str, str],
):
    connect_calls.append((url, headers))
    return socket


def test_config_sync_client_records_latest_versions() -> None:
    seen: list[tuple[str, int]] = []
    client = ConfigSyncClient(fetcher=lambda agent_id, profile_version: seen.append((agent_id, profile_version)))

    request = client.handle_notification({"agent_id": "agent-a", "profile_version": 3})

    assert request.agent_id == "agent-a"
    assert client.latest_profile_version("agent-a") == 3
    assert seen == [("agent-a", 3)]


def test_im_connection_connects_registers_and_handles_downstream_frames(tmp_path: Path) -> None:
    inbound_seen = []
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
            json.dumps({"type": "config.sync", "payload": {"agent_id": "agent-a", "profile_version": 5}}),
            json.dumps({"type": "heartbeat.trigger", "payload": {"agent_id": "agent-a", "reason": "manual"}}),
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
        heartbeat_trigger=lambda agent_id, reason: heartbeat_seen.append((agent_id, reason)),
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


def test_im_connection_sends_periodic_node_heartbeats_while_connected(tmp_path: Path) -> None:
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    socket = _FakeWebSocket(incoming=[json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})])
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000", heartbeat_interval_seconds=0.01),
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
    assert [json.loads(frame)["type"] for frame in first_socket.sent] == ["node.register"]
    assert [json.loads(frame)["type"] for frame in second_socket.sent] == ["node.register", "node.report"]
    assert json.loads(second_socket.sent[1])["payload"] == {"run_id": "run-1", "status": "running"}


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
        incoming=[json.dumps({"type": "ack", "payload": {"message_type": "node.report", "node_id": "node-1"}})]
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
        await manager.send_json("node.report", {"run_id": "run-1", "status": "completed"})
        assert manager._awaiting_ack_type == "node.report"  # noqa: SLF001
        assert [json.loads(frame)["type"] for frame in first_socket.sent] == ["node.register", "node.report"]
        await manager._disconnect_current_websocket(RuntimeError("socket dropped"))  # noqa: SLF001
        await manager.connect_once()
        assert [json.loads(frame)["type"] for frame in second_socket.sent] == ["node.register", "node.report"]
        await manager._listen_once()  # noqa: SLF001
        assert manager._awaiting_ack_type is None  # noqa: SLF001
        assert list(manager._pending_frames) == []  # noqa: SLF001

    asyncio.run(_exercise())


def test_im_connection_retries_with_exponential_backoff_until_cap(tmp_path: Path) -> None:
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
        config=IMConnectionConfig(url="http://im.local:9000", reconnect_initial_seconds=1.0, reconnect_max_seconds=5.0),
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
        ack_task = asyncio.create_task(manager.send_agent_message({"to": "user-1", "text": "hi"}))
        await asyncio.sleep(0)
        await manager._listen_once()  # noqa: SLF001 - consume agent.message ack
        ack = await ack_task
        assert ack.conversation_id == "conv-direct-1"
        assert ack.message_id == "msg-1"
        assert ack.target_kind == "user_id"
        assert ack.target_id == "user-1"
        assert ack.source_agent_id == "agent-a"

    asyncio.run(_exercise())


def test_im_connection_send_json_await_ack_returns_raw_ack_payload(tmp_path: Path) -> None:
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
            json.dumps({"type": "ack", "payload": {"message_type": "node.report", "status": "ok", "run_id": "run-1"}}),
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
        ack_task = asyncio.create_task(manager.send_json_await_ack("node.report", {"run_id": "run-1"}))
        await asyncio.sleep(0)
        await manager._listen_once()  # noqa: SLF001
        ack = await ack_task
        assert ack == {"message_type": "node.report", "status": "ok", "run_id": "run-1"}

    asyncio.run(_exercise())


def test_im_connection_send_agent_message_fails_when_socket_drops_before_ack(tmp_path: Path) -> None:
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1"),
        agents=_agents(tmp_path),
        send_frame=lambda _message_type, _payload: None,
    )
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    socket = _FakeWebSocket(incoming=[json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})])
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=reporter,
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        task = asyncio.create_task(manager.send_agent_message({"to": "user-1", "text": "hi"}))
        await asyncio.sleep(0)
        await manager._disconnect_current_websocket(RuntimeError("socket dropped"))  # noqa: SLF001
        with pytest.raises(RuntimeError, match="before ack"):
            await task
        assert len(manager._pending_frames) == 1  # noqa: SLF001
        assert manager._pending_frames[0].message_type == "agent.message"  # noqa: SLF001

    asyncio.run(_exercise())
