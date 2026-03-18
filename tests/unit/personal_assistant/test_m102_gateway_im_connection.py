from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from collections import deque
from pathlib import Path

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from agent.products.personal_assistant.tools.send_message import SendMessageTool
from personal_assistant.channels.web_relay_adapter import RelayDeduplicationStore, WebRelayAdapter
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
    return (AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace, title="Agent A"),)


def test_upstream_reporter_builds_register_heartbeat_report_and_receipt(tmp_path: Path) -> None:
    frames: list[tuple[str, dict[str, object]]] = []
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1", user_id="user-1"),
        agents=_agents(tmp_path),
        send_frame=lambda message_type, payload: frames.append((message_type, payload)),
        node_name="MacBook",
        version="1.2.3",
    )

    register = reporter.send_register()
    heartbeat = reporter.send_heartbeat(status="online", last_error=None, extra={"running_runs": 2})
    report = reporter.send_report(run_id="run-1", status="completed", agent_id="agent-a", session_key="web:user:agent-a")
    receipt = reporter.send_delivery_receipt(relay_task_id="relay-1", delivery_status="completed", detail="ok")

    assert register["node_id"] == "node-1"
    assert register["agents"] == ["agent-a"]
    assert heartbeat["running_runs"] == 2
    assert report["run_id"] == "run-1"
    assert receipt["relay_task_id"] == "relay-1"
    assert [item[0] for item in frames] == [
        "node.register",
        "node.heartbeat",
        "node.report",
        "node.delivery_receipt",
    ]


def test_web_relay_adapter_converts_relay_payload_to_inbound_message() -> None:
    adapter = WebRelayAdapter()
    seen: list[InboundMessage] = []
    adapter.start(seen.append)

    inbound = adapter.accept_relay(
        {
            "relay_task_id": "relay-1",
            "idempotency_key": "idem-1",
            "agent_id": "agent-a",
            "message": {
                "id": "msg-1",
                "sender_user_id": "user-1",
                "conversation_id": "conv-1",
                "content": "hello gateway",
            },
            "metadata": {"conversation_type": "group", "thread_id": "thread-1"},
        }
    )

    assert inbound == seen[0]
    assert inbound.channel_name == "web_relay"
    assert inbound.external_chat_id == "conv-1"
    assert inbound.is_group is True
    assert inbound.metadata["relay_task_id"] == "relay-1"
    assert inbound.metadata["message_id"] == "msg-1"

    adapter.send(
        OutboundMessage(
            channel_name="web_relay",
            text="reply",
            target_chat_id="conv-1",
        )
    )
    assert adapter.sent[0].text == "reply"


def test_relay_dedup_store_contains_after_add(tmp_path: Path) -> None:
    store = RelayDeduplicationStore(db_path=tmp_path / "relay-dedup.sqlite3")

    store.add("idem-1")

    assert store.contains("idem-1") is True



def test_relay_dedup_store_load_from_db_populates_deque(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    store = RelayDeduplicationStore(db_path=db_path)
    store.add("idem-1")

    reloaded = RelayDeduplicationStore(db_path=db_path)
    reloaded.load_from_db()

    assert reloaded.contains("idem-1") is True



def test_relay_dedup_store_expired_keys_not_loaded(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    store = RelayDeduplicationStore(db_path=db_path, ttl_seconds=1)
    store.add("idem-expired")
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE relay_deduplication_keys SET expires_at = ?", (time.time() - 10,))
        conn.commit()

    reloaded = RelayDeduplicationStore(db_path=db_path)
    reloaded.load_from_db()

    assert reloaded.contains("idem-expired") is False



def test_relay_dedup_store_purge_removes_expired_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    store = RelayDeduplicationStore(db_path=db_path, ttl_seconds=30)
    store.add("idem-expired")
    store.add("idem-live")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE relay_deduplication_keys SET expires_at = ? WHERE idempotency_key = ?",
            (time.time() - 10, "idem-expired"),
        )
        conn.commit()

    deleted = store.purge_expired()

    assert deleted == 1
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT idempotency_key FROM relay_deduplication_keys ORDER BY idempotency_key"
        ).fetchall()
    assert rows == [("idem-live",)]



def test_relay_dedup_store_deque_rolls_over_at_max(tmp_path: Path) -> None:
    store = RelayDeduplicationStore(db_path=tmp_path / "relay-dedup.sqlite3", seen_keys=deque(["old"]))
    store._seen_idempotency_keys = deque([str(index) for index in range(1000)])  # noqa: SLF001

    store.add("overflow")

    assert store.contains("0") is False
    assert store.contains("overflow") is True
    assert len(store._seen_idempotency_keys) == 1000  # noqa: SLF001


def test_web_relay_adapter_uses_dedup_store_on_accept(tmp_path: Path) -> None:
    store = RelayDeduplicationStore(db_path=tmp_path / "relay-dedup.sqlite3")
    adapter = WebRelayAdapter(dedup_store=store)
    seen: list[InboundMessage] = []
    adapter.start(seen.append)
    payload = {
        "relay_task_id": "relay-1",
        "idempotency_key": "idem-1",
        "message": {
            "id": "msg-1",
            "sender_user_id": "user-1",
            "conversation_id": "conv-1",
            "content": "hello gateway",
        },
        "metadata": {"conversation_type": "direct"},
    }

    adapter.accept_relay(payload)
    adapter.accept_relay(payload)

    assert [item.text for item in seen] == ["hello gateway"]
    reloaded = RelayDeduplicationStore(db_path=tmp_path / "relay-dedup.sqlite3")
    reloaded.load_from_db()
    assert reloaded.contains("idem-1") is True



def test_web_relay_adapter_loads_store_on_start(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    seeded = RelayDeduplicationStore(db_path=db_path)
    seeded.add("idem-1")
    adapter = WebRelayAdapter(dedup_store=RelayDeduplicationStore(db_path=db_path))

    adapter.start(lambda _message: None)

    assert adapter._seen_idempotency_keys == deque(["idem-1"])  # noqa: SLF001



def test_web_relay_adapter_without_store_uses_in_memory_dedup() -> None:
    adapter = WebRelayAdapter()
    seen: list[InboundMessage] = []
    adapter.start(seen.append)
    payload = {
        "relay_task_id": "relay-1",
        "idempotency_key": "idem-1",
        "message": {
            "id": "msg-1",
            "sender_user_id": "user-1",
            "conversation_id": "conv-1",
            "content": "hello gateway",
        },
        "metadata": {"conversation_type": "direct"},
    }

    adapter.accept_relay(payload)
    adapter.accept_relay(payload)

    assert [item.text for item in seen] == ["hello gateway"]



def test_config_sync_client_records_latest_versions() -> None:
    seen: list[tuple[str, int]] = []
    client = ConfigSyncClient(fetcher=lambda agent_id, profile_version: seen.append((agent_id, profile_version)))

    request = client.handle_notification({"agent_id": "agent-a", "profile_version": 3})

    assert request.agent_id == "agent-a"
    assert client.latest_profile_version("agent-a") == 3
    assert seen == [("agent-a", 3)]


def test_im_connection_connects_registers_and_handles_downstream_frames(tmp_path: Path) -> None:
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


def test_send_message_tool_dispatches_via_gateway_boundary() -> None:
    seen: list[dict[str, object]] = []

    class _Dispatcher:
        def send_message(self, *, text: str, to: str, session_id: str | None = None):
            payload = {"text": text, "to": to, "session_id": session_id, "route": "local"}
            seen.append(payload)
            return payload

    tool = SendMessageTool(dispatcher=_Dispatcher())
    from agent.core.tools.base import ToolContext
    from pathlib import Path as _Path
    from agent.core.tools.base import set_tool_safety_config_factory, set_tool_safety_factory

    class _Safety:
        def __init__(self, *, repo_root, config):  # noqa: ANN001
            self.repo_root = repo_root
            self.config = config

    class _SafetyConfig:
        pass

    set_tool_safety_factory(_Safety)
    set_tool_safety_config_factory(_SafetyConfig)
    ctx = ToolContext.create(repo_root=_Path("/tmp")).with_session("sess-1")

    result = tool.run({"text": "hello", "to": "agent-b"}, ctx)

    assert result["ok"] is True
    assert seen == [{"text": "hello", "to": "agent-b", "session_id": "sess-1", "route": "local"}]


async def _connect_fake(
    socket: _FakeWebSocket,
    connect_calls: list[tuple[str, dict[str, str]]],
    url: str,
    headers: dict[str, str],
):
    connect_calls.append((url, headers))
    return socket
