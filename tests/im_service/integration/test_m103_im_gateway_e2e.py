"""M103 browserless IM ↔ Gateway end-to-end integration coverage."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import AgentProfileRepository, NodeRepository, UserRepository
from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore


class _FakeKernelClient:
    """Record gateway->kernel calls and synthesize deterministic replies."""

    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, str | None]] = []
        self.send_calls: list[dict[str, str]] = []
        self.run_states: dict[str, dict[str, str]] = {}
        self._session_index = 0
        self._run_index = 0

    def create_session(self, *, workspace_root: str, product_id: str, title: str | None = None):
        self._session_index += 1
        session_id = f"sess-{self._session_index}"
        self.create_session_calls.append(
            {"workspace_root": workspace_root, "product_id": product_id, "title": title}
        )
        return {"session_id": session_id}

    def send_message_async(self, *, session_id: str, text: str):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        self.send_calls.append({"session_id": session_id, "text": text, "run_id": run_id})
        self.run_states[run_id] = {"run_id": run_id, "output_text": f"gateway-reply:{text}"}
        return {"run_id": run_id}

    def get_run(self, *, run_id: str):
        return self.run_states[run_id]


def _seed_user(client: TestClient, username: str, display_name: str | None = None) -> str:
    response = client.post(
        "/im/v1/users",
        json={"username": username, "display_name": display_name or username.title()},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _seed_node_and_profiles(app, *, owner_id: str = "", agent_ids: tuple[str, ...] = ("agent-a",)) -> None:
    nodes = NodeRepository(app.state.connection)
    nodes.upsert_node(node_id="node-1", node_name="MacBook")
    profiles = AgentProfileRepository(app.state.connection)
    for agent_id in agent_ids:
        profiles.upsert_profile(
            agent_id=agent_id,
            owner_id=owner_id,
            display_name=agent_id,
            description=f"profile for {agent_id}",
            system_prompt=f"You are {agent_id}.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-1", agent_id),
        )
    app.state.connection.commit()


def _agents(tmp_path: Path, *agent_ids: str) -> tuple[AgentWorkspaceConfig, ...]:
    agents: list[AgentWorkspaceConfig] = []
    for agent_id in agent_ids:
        workspace_root = tmp_path / agent_id
        workspace_root.mkdir()
        agents.append(
            AgentWorkspaceConfig(agent_id=agent_id, workspace_root=workspace_root, title=agent_id.title())
        )
    return tuple(agents)


def test_web_im_message_roundtrip_browserless(tmp_path: Path) -> None:
    """Send a Web IM message through IM websocket, gateway pipeline, and reply channel."""
    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = _agents(tmp_path, "agent-a")
    registry = ChannelRegistry((relay_adapter,))
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        user_id = _seed_user(client, "alice")
        _seed_node_and_profiles(app, agent_ids=("agent-a",))
        conversation = client.post(
            "/im/v1/conversations",
            json={"title": "web-chat", "participant_ids": [user_id]},
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-a"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            created = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-m103-roundtrip"},
                json={
                    "sender_user_id": user_id,
                    "content": "hello gateway",
                    "target_node_id": "node-1",
                },
            )
            assert created.status_code == 201
            relay_frame = websocket.receive_json()
            assert relay_frame["type"] == "relay.message"
            relay_adapter.accept_relay(relay_frame["payload"])

    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agents[0].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent-A",
        }
    ]
    assert kernel_client.send_calls == [
        {"session_id": "sess-1", "text": "hello gateway", "run_id": "run-1"}
    ]
    assert relay_adapter.sent == [
        OutboundMessage(
            channel_name="web_relay",
            text="gateway-reply:hello gateway",
            target_chat_id=conversation_id,
            thread_id=None,
            metadata={
                "relay_task_id": relay_frame["payload"]["relay_task_id"],
                "idempotency_key": "idem-m103-roundtrip",
            },
        )
    ]


def test_device_binding_end_to_end_updates_node_and_agent_owner(tmp_path: Path) -> None:
    """Bind one node to one user and propagate ownership to node-local agents."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner_id = _seed_user(client, "owner", "Owner")
        _seed_node_and_profiles(app, agent_ids=("agent-a", "agent-b"))

        start = client.post("/im/v1/bind", json={"action": "start", "node_id": "node-1"})
        assert start.status_code == 201
        bind_id = start.json()["bind_id"]

        confirm = client.post(
            "/im/v1/bind",
            json={"action": "confirm", "bind_id": bind_id, "user_id": owner_id},
        )
        assert confirm.status_code == 201
        assert confirm.json()["status"] == "confirmed"

        me = client.get(f"/im/v1/me?user_id={owner_id}")
        assert me.status_code == 200
        assert me.json()["owned_node_ids"] == ["node-1"]

        profile_a = client.get("/im/v1/agents/agent-a/config")
        profile_b = client.get("/im/v1/agents/agent-b/config")
        assert profile_a.status_code == 200
        assert profile_b.status_code == 200
        assert profile_a.json()["owner_id"] == me.json()["owner_id"]
        assert profile_b.json()["owner_id"] == me.json()["owner_id"]


def test_agent_config_sync_notifies_connected_gateway(tmp_path: Path) -> None:
    """Push config.sync after a profile update and let the gateway record the version."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner_id = _seed_user(client, "owner")
        _seed_node_and_profiles(app, owner_id=UserRepository(app.state.connection).get_user(user_id=owner_id).owner_id)
        sync_client = ConfigSyncClient()

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-a"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            websocket.receive_json()

            current = client.get("/im/v1/agents/agent-a/config")
            assert current.status_code == 200
            patched = client.patch(
                "/im/v1/agents/agent-a/config",
                json={
                    "profile_version": current.json()["profile_version"],
                    "display_name": "agent-a v2",
                    "description": "updated",
                    "system_prompt": "You are upgraded.",
                    "skills": ["plan"],
                    "tool_allowlist": ["read"],
                    "group_reply_policy": "manual",
                    "default_model": "claude-sonnet-4",
                },
            )
            assert patched.status_code == 200
            pushed = asyncio.run(
                app.state.gateway_handler.push_config_sync(
                    target_node_id="node-1",
                    agent_id="agent-a",
                    profile_version=patched.json()["profile_version"],
                )
            )
            assert pushed is True
            frame = websocket.receive_json()
            assert frame == {
                "type": "config.sync",
                "payload": {"agent_id": "agent-a", "profile_version": 2},
            }
            request = sync_client.handle_notification(frame["payload"])

    assert request.agent_id == "agent-a"
    assert sync_client.latest_profile_version("agent-a") == 2
