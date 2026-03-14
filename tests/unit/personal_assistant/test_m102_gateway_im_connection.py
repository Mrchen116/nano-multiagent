from __future__ import annotations

import asyncio
import json
from pathlib import Path

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from agent.products.personal_assistant.tools.send_message import SendMessageTool
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
