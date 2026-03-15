"""M103 browserless IM ↔ Gateway end-to-end integration coverage."""

from __future__ import annotations

import asyncio
import json
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
        self.create_session_calls: list[dict[str, object | None]] = []
        self.send_calls: list[dict[str, str]] = []
        self.run_states: dict[str, dict[str, str] | list[dict[str, str]]] = {}
        self.session_events: dict[str, list[list[dict[str, object]]]] = {}
        self._session_metadata_by_id: dict[str, dict[str, object | None]] = {}
        self._session_index = 0
        self._run_index = 0
        self._get_run_calls: dict[str, int] = {}
        self._stream_calls: dict[str, int] = {}

    def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ):
        self._session_index += 1
        session_id = f"sess-{self._session_index}"
        self.create_session_calls.append(
            {"workspace_root": workspace_root, "product_id": product_id, "title": title, "metadata": metadata}
        )
        self._session_metadata_by_id[session_id] = dict(metadata or {})
        self.session_events.setdefault(session_id, [])
        return {"session_id": session_id}

    def send_message_async(self, *, session_id: str, text: str):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        self.send_calls.append({"session_id": session_id, "text": text, "run_id": run_id})
        session_metadata = self._session_metadata_by_id.get(session_id, {})
        output_text = f"gateway-reply:{text}"
        if text == "@agent-a please stay silent if NO_REPLY works.":
            system_prompt = session_metadata.get("system_prompt")
            profile_version = session_metadata.get("config_profile_version")
            if (
                system_prompt == "When mentioned in a group chat, reply exactly with NO_REPLY."
                and profile_version == 2
            ):
                output_text = "NO_REPLY"
            elif system_prompt == "When mentioned in a group chat, reply exactly with NO_REPLY.":
                output_text = "ALPHA_ACK_M170"
        self.run_states[run_id] = {"run_id": run_id, "output_text": output_text}
        return {"run_id": run_id}

    def stream_session_events(self, *, session_id: str, max_events: int = 20, timeout_seconds: float = 0.25):
        del max_events
        del timeout_seconds
        batches = self.session_events.get(session_id, [])
        index = self._stream_calls.get(session_id, 0)
        self._stream_calls[session_id] = index + 1
        if index >= len(batches):
            return []
        return batches[index]

    def get_run(self, *, run_id: str):
        payload = self.run_states[run_id]
        if isinstance(payload, list):
            index = self._get_run_calls.get(run_id, 0)
            self._get_run_calls[run_id] = index + 1
            if index >= len(payload):
                return payload[-1]
            return payload[index]
        return payload


def test_fake_kernel_client_send_message_async_seeds_terminal_run_snapshot() -> None:
    """The browserless M103 fixture must mirror terminal run snapshots from the real kernel API."""
    kernel_client = _FakeKernelClient()

    created = kernel_client.create_session(
        workspace_root="/tmp/agent-a",
        product_id="personal_assistant",
        title="Agent-A",
    )
    submitted = kernel_client.send_message_async(session_id=created["session_id"], text="hello gateway")
    run_state = kernel_client.get_run(run_id=submitted["run_id"])

    assert run_state["status"] == "completed"
    assert run_state["output_text"] == "gateway-reply:hello gateway"



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
            workspace_root=None,
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


def test_gateway_registration_materializes_runtime_agents_before_and_after_bind(tmp_path: Path) -> None:
    """Gateway-advertised agents should be selectable in fresh runtime and reassigned after bind."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user = client.post("/im/v1/users", json={"username": "you", "display_name": "You"})
        assert user.status_code == 201

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["Alpha", "Beta"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            before_bind = client.get("/im/v1/agents")
            assert before_bind.status_code == 200
            assert [item["agent_id"] for item in before_bind.json()] == ["Alpha", "Beta"]
            assert [item["bound_nodes"] for item in before_bind.json()] == [["node-1"], ["node-1"]]
            assert [item["owner_id"] for item in before_bind.json()] == ["", ""]

            bind_start = client.post("/im/v1/bind", json={"action": "start", "node_id": "node-1"})
            assert bind_start.status_code == 201
            bind_confirm = client.post(
                "/im/v1/bind",
                json={
                    "action": "confirm",
                    "bind_id": bind_start.json()["bind_id"],
                    "user_id": user.json()["id"],
                },
            )
            assert bind_confirm.status_code == 201

            listed = client.get("/im/v1/agents")
            assert listed.status_code == 200
            assert [item["agent_id"] for item in listed.json()] == ["Alpha", "Beta"]
            assert [item["bound_nodes"] for item in listed.json()] == [["node-1"], ["node-1"]]
            assert [item["owner_id"] for item in listed.json()] == [user.json()["owner_id"], user.json()["owner_id"]]


def test_gateway_reregistration_preserves_canonical_agent_labels_after_restart(tmp_path: Path) -> None:
    """Fresh re-registration should rebuild canonical agent labels instead of leaving raw ids in the picker."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-m170-alpha", "agent-m170-beta"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

        first_listing = client.get("/im/v1/agents")
        assert first_listing.status_code == 200
        assert [item["display_name"] for item in first_listing.json()] == ["M170 Alpha", "M170 Beta"]

        app.state.connection.execute("DELETE FROM agent_profiles WHERE agent_id IN (?, ?)", ("agent-m170-alpha", "agent-m170-beta"))
        app.state.connection.commit()

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.1",
                        "agents": ["agent-m170-alpha", "agent-m170-beta"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

        second_listing = client.get("/im/v1/agents")
        assert second_listing.status_code == 200
        assert [item["agent_id"] for item in second_listing.json()] == ["agent-m170-alpha", "agent-m170-beta"]
        assert [item["display_name"] for item in second_listing.json()] == ["M170 Alpha", "M170 Beta"]



def test_fresh_runtime_agents_can_back_group_creation_before_bind(tmp_path: Path) -> None:
    """A fresh gateway runtime should expose agents early enough for real group creation."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user_id = _seed_user(client, "alice")

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["Alpha", "Beta"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            listed = client.get("/im/v1/agents")
            assert listed.status_code == 200
            assert [item["agent_id"] for item in listed.json()] == ["Alpha", "Beta"]

            agent_a_user = client.post("/im/v1/users", json={"username": "agent:Alpha", "display_name": "Alpha"})
            agent_b_user = client.post("/im/v1/users", json={"username": "agent:Beta", "display_name": "Beta"})
            assert agent_a_user.status_code == 201
            assert agent_b_user.status_code == 201

            created = client.post(
                "/im/v1/conversations",
                json={
                    "title": "Fresh Runtime Group",
                    "participant_ids": [user_id, agent_a_user.json()["id"], agent_b_user.json()["id"]],
                },
            )
            assert created.status_code == 201
            body = created.json()
            assert body["type"] == "group"
            assert set(body["participant_ids"]) == {user_id, agent_a_user.json()["id"], agent_b_user.json()["id"]}



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
        agent_user_id = _seed_user(client, "agent:agent-a")
        _seed_node_and_profiles(app, agent_ids=("agent-a",))
        conversation = client.post(
            "/im/v1/conversations",
            json={"title": "web-chat", "participant_ids": [user_id, agent_user_id]},
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
            "metadata": {
                "agent_id": "agent-a",
                "config_profile_version": 1,
                "system_prompt": "You are agent-a.",
            },
        }
    ]
    assert kernel_client.send_calls == [
        {"session_id": "sess-1", "text": "hello gateway", "run_id": "run-1"}
    ]
    assert relay_frame["payload"]["agent_id"] == "agent-a"
    assert relay_frame["payload"]["metadata"] == {
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 1,
        "system_prompt": "You are agent-a.",
    }
    assert relay_adapter.sent == [
        OutboundMessage(
            channel_name="web_relay",
            text="gateway-reply:hello gateway",
            target_chat_id=conversation_id,
            thread_id=None,
            metadata={
                "relay_task_id": relay_frame["payload"]["relay_task_id"],
                "idempotency_key": "idem-m103-roundtrip",
                "message_id": relay_frame["payload"]["message"]["id"],
                "conversation_type": "direct",
                "mentioned_agent_ids": [],
                "config_profile_version": 1,
                "system_prompt": "You are agent-a.",
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
    """Push config.sync automatically after a profile update."""
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
            frame = websocket.receive_json()
            assert frame == {
                "type": "config.sync",
                "payload": {"agent_id": "agent-a", "profile_version": 2},
            }
            request = sync_client.handle_notification(frame["payload"])

    assert request.agent_id == "agent-a"
    assert sync_client.latest_profile_version("agent-a") == 2



def test_group_chat_uses_live_updated_profile_after_config_sync_in_same_conversation(tmp_path: Path) -> None:
    """An existing group conversation must use the updated mentioned-agent profile after config sync."""
    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = _agents(tmp_path, "agent-a", "agent-b")
    registry = ChannelRegistry((relay_adapter,))
    session_store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=session_store,
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        owner_id = _seed_user(client, "owner")
        human_user_id = _seed_user(client, "alice")
        agent_a_user_id = _seed_user(client, "agent:agent-a")
        agent_b_user_id = _seed_user(client, "agent:agent-b")
        owner = UserRepository(app.state.connection).get_user(user_id=owner_id)
        assert owner is not None
        _seed_node_and_profiles(app, owner_id=owner.owner_id, agent_ids=("agent-a", "agent-b"))

        group_conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "same group",
                "participant_ids": [human_user_id, agent_a_user_id, agent_b_user_id],
            },
        )
        assert group_conversation.status_code == 201
        assert group_conversation.json()["config_profile_version"] == 1
        conversation_id = group_conversation.json()["id"]

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-a", "agent-b"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            first_message = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-before-sync"},
                json={
                    "sender_user_id": human_user_id,
                    "content": "@agent-a first mention",
                    "target_node_id": "node-1",
                },
            )
            assert first_message.status_code == 201
            first_relay = websocket.receive_json()
            relay_adapter.accept_relay(first_relay["payload"])
            assert websocket.receive_json()["payload"]["delivery_status"] == "sent"
            first_completed = websocket.receive_json()
            assert first_completed["payload"]["delivery_status"] == "completed"
            assert first_completed["payload"]["detail"] == "gateway-reply:@agent-a first mention"

            current = client.get("/im/v1/agents/agent-a/config")
            assert current.status_code == 200
            patched = client.patch(
                "/im/v1/agents/agent-a/config",
                json={
                    "profile_version": current.json()["profile_version"],
                    "display_name": "agent-a v2",
                    "description": "updated",
                    "system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY.",
                    "skills": [],
                    "tool_allowlist": [],
                    "group_reply_policy": "manual",
                    "default_model": None,
                },
            )
            assert patched.status_code == 200
            sync_frame = websocket.receive_json()
            assert sync_frame == {
                "type": "config.sync",
                "payload": {"agent_id": "agent-a", "profile_version": 2},
            }
            pipeline.drop_agent_sessions("agent-a")

            second_message = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-after-sync"},
                json={
                    "sender_user_id": human_user_id,
                    "content": "@agent-a please stay silent if NO_REPLY works.",
                    "target_node_id": "node-1",
                },
            )
            assert second_message.status_code == 201
            second_relay = websocket.receive_json()
            relay_adapter.accept_relay(second_relay["payload"])
            assert websocket.receive_json()["payload"]["delivery_status"] == "sent"
            second_completed = websocket.receive_json()
            assert second_completed["payload"]["delivery_status"] == "completed"
            assert second_completed["payload"]["detail"] == "NO_REPLY | suppressed_by=no_reply_token"

    assert [call["metadata"] for call in kernel_client.create_session_calls] == [
        {
            "agent_id": "agent-a",
            "conversation_id": conversation_id,
            "config_profile_version": 1,
            "system_prompt": "You are agent-a.",
        },
        {
            "agent_id": "agent-a",
            "conversation_id": conversation_id,
            "config_profile_version": 2,
            "system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY.",
        },
    ]
    assert [call["session_id"] for call in kernel_client.send_calls] == ["sess-1", "sess-2"]
    assert first_relay["payload"]["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-a"],
        "config_profile_version": 1,
        "system_prompt": "You are agent-a.",
    }
    assert second_relay["payload"]["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-a"],
        "config_profile_version": 2,
        "system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY.",
    }
    assert relay_adapter.sent[0].text == "gateway-reply:@agent-a first mention"
    assert relay_adapter.sent == [relay_adapter.sent[0]]


def test_group_chat_keeps_no_reply_when_completed_snapshot_and_late_stream_delta_conflict(tmp_path: Path) -> None:
    """Completed NO_REPLY snapshots must win over stale streamed text in the same relay chain."""
    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = _agents(tmp_path, "agent-a")
    registry = ChannelRegistry((relay_adapter,))
    session_store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=session_store,
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        owner_id = _seed_user(client, "owner")
        human_user_id = _seed_user(client, "alice")
        agent_a_user_id = _seed_user(client, "agent:agent-a")
        owner = UserRepository(app.state.connection).get_user(user_id=owner_id)
        assert owner is not None
        _seed_node_and_profiles(app, owner_id=owner.owner_id, agent_ids=("agent-a",))

        current = client.get("/im/v1/agents/agent-a/config")
        assert current.status_code == 200
        patched = client.patch(
            "/im/v1/agents/agent-a/config",
            json={
                "profile_version": current.json()["profile_version"],
                "display_name": "agent-a v2",
                "description": "updated",
                "system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY.",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "manual",
                "default_model": None,
            },
        )
        assert patched.status_code == 200

        group_conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "same group",
                "participant_ids": [human_user_id, agent_a_user_id],
            },
        )
        assert group_conversation.status_code == 201
        conversation_id = group_conversation.json()["id"]

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

            second_message = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-after-sync-stream-conflict"},
                json={
                    "sender_user_id": human_user_id,
                    "content": "@agent-a please stay silent if NO_REPLY works.",
                    "target_node_id": "node-1",
                },
            )
            assert second_message.status_code == 201
            second_relay = websocket.receive_json()
            relay_task_id = second_relay["payload"]["relay_task_id"]
            message_id = second_relay["payload"]["message"]["id"]
            kernel_client.session_events["sess-1"] = [
                [{"id": "evt-1", "event": "text_delta", "data": {"run_id": "run-1", "delta": "ALPHA_ACK_M170"}}],
                [{"id": "evt-2", "event": "text_delta", "data": {"run_id": "run-1", "delta": "ALPHA_ACK_M170 final"}}],
            ]
            kernel_client.run_states["run-1"] = [
                {"run_id": "run-1", "status": "running", "output_text": "NO_REPLY"},
                {"run_id": "run-1", "status": "completed", "output_text": "NO_REPLY", "error": None},
            ]
            relay_adapter.accept_relay(second_relay["payload"])
            assert websocket.receive_json()["payload"]["delivery_status"] == "sent"
            second_completed = websocket.receive_json()
            assert second_completed["payload"]["delivery_status"] == "completed"
            assert second_completed["payload"]["detail"] == "NO_REPLY | suppressed_by=no_reply_token"

    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agents[0].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent-A",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": conversation_id,
                "config_profile_version": 2,
                "system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY.",
            },
        }
    ]
    assert kernel_client.send_calls == [
        {"session_id": "sess-1", "text": "@agent-a please stay silent if NO_REPLY works.", "run_id": "run-1"}
    ]
    assert second_relay["payload"]["relay_task_id"] == relay_task_id
    assert second_relay["payload"]["message"]["id"] == message_id
    assert relay_adapter.sent == []


def test_direct_chat_keeps_old_session_after_config_sync_while_new_conversation_gets_new_profile(tmp_path: Path) -> None:
    """Old direct conversations stay pinned while new conversations pick up synced config."""
    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = _agents(tmp_path, "agent-a")
    registry = ChannelRegistry((relay_adapter,))
    session_store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=session_store,
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        owner_id = _seed_user(client, "owner")
        human_user_id = _seed_user(client, "alice")
        agent_user_id = _seed_user(client, "agent:agent-a")
        owner = UserRepository(app.state.connection).get_user(user_id=owner_id)
        assert owner is not None
        _seed_node_and_profiles(app, owner_id=owner.owner_id)

        old_conversation = client.post(
            "/im/v1/conversations",
            json={"title": "old direct", "participant_ids": [human_user_id, agent_user_id]},
        )
        assert old_conversation.status_code == 201
        assert old_conversation.json()["config_profile_version"] == 1
        old_conversation_id = old_conversation.json()["id"]

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

            def _complete_relay(relay_frame: dict[str, object], *, detail: str) -> None:
                relay_payload = relay_frame["payload"]
                websocket.send_json(
                    {
                        "type": "node.delivery_receipt",
                        "payload": {
                            "node_id": "node-1",
                            "relay_task_id": relay_payload["relay_task_id"],
                            "delivery_status": "completed",
                            "detail": detail,
                        },
                    }
                )
                receipt_ack = websocket.receive_json()
                assert receipt_ack == {
                    "type": "ack",
                    "payload": {
                        "message_type": "node.delivery_receipt",
                        "node_id": "node-1",
                        "relay_task_id": relay_payload["relay_task_id"],
                        "status": "completed",
                    },
                }

            sync = ConfigSyncClient()
            old_before = client.post(
                f"/im/v1/conversations/{old_conversation_id}/messages",
                headers={"Idempotency-Key": "idem-m150-old-before"},
                json={
                    "sender_user_id": human_user_id,
                    "content": "hello before sync",
                    "target_node_id": "node-1",
                },
            )
            assert old_before.status_code == 201
            first_relay = websocket.receive_json()
            relay_adapter.accept_relay(first_relay["payload"])
            _complete_relay(first_relay, detail="old-before-complete")

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
            sync_frame = websocket.receive_json()
            request = sync.handle_notification(sync_frame["payload"])
            assert request.agent_id == "agent-a"
            refreshed_workspace = tmp_path / "agent-a-refreshed"
            refreshed_workspace.mkdir()
            pipeline.register_agent(
                AgentWorkspaceConfig(
                    agent_id="agent-a",
                    workspace_root=refreshed_workspace,
                    title="agent-a v2",
                )
            )

            old_after = client.post(
                f"/im/v1/conversations/{old_conversation_id}/messages",
                headers={"Idempotency-Key": "idem-m150-old-after"},
                json={
                    "sender_user_id": human_user_id,
                    "content": "hello after sync old",
                    "target_node_id": "node-1",
                },
            )
            assert old_after.status_code == 201
            old_after_relay = websocket.receive_json()
            relay_adapter.accept_relay(old_after_relay["payload"])
            _complete_relay(old_after_relay, detail="old-after-complete")

            new_conversation = client.post(
                "/im/v1/conversations",
                json={"title": "new direct", "participant_ids": [human_user_id, agent_user_id]},
            )
            assert new_conversation.status_code == 201
            assert new_conversation.json()["config_profile_version"] == 2
            new_conversation_id = new_conversation.json()["id"]

            new_after = client.post(
                f"/im/v1/conversations/{new_conversation_id}/messages",
                headers={"Idempotency-Key": "idem-m150-new-after"},
                json={
                    "sender_user_id": human_user_id,
                    "content": "hello after sync new",
                    "target_node_id": "node-1",
                },
            )
            assert new_after.status_code == 201
            new_after_relay = websocket.receive_json()
            relay_adapter.accept_relay(new_after_relay["payload"])
            _complete_relay(new_after_relay, detail="new-after-complete")

        old_event_rows = app.state.connection.execute(
            """
            SELECT event_type, payload_json
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (old_conversation_id,),
        ).fetchall()
        new_event_rows = app.state.connection.execute(
            """
            SELECT event_type, payload_json
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (new_conversation_id,),
        ).fetchall()
        old_completed_payloads = [
            json.loads(row["payload_json"])
            for row in old_event_rows
            if row["event_type"] == "relay.completed"
        ]
        new_completed_payloads = [
            json.loads(row["payload_json"])
            for row in new_event_rows
            if row["event_type"] == "relay.completed"
        ]

    assert [call["metadata"] for call in kernel_client.create_session_calls] == [
        {
            "agent_id": "agent-a",
            "config_profile_version": 1,
            "system_prompt": "You are agent-a.",
        },
        {
            "agent_id": "agent-a",
            "config_profile_version": 2,
            "system_prompt": "You are upgraded.",
        },
    ]
    assert [call["title"] for call in kernel_client.create_session_calls] == ["Agent-A", "agent-a v2"]
    assert [call["workspace_root"] for call in kernel_client.create_session_calls] == [
        str(agents[0].workspace_root),
        str(tmp_path / "agent-a-refreshed"),
    ]
    assert [call["session_id"] for call in kernel_client.send_calls] == ["sess-1", "sess-1", "sess-2"]
    assert session_store.get(f"web_relay:{old_conversation_id}:agent-a").kernel_session_id == "sess-1"
    assert session_store.get(f"web_relay:{new_conversation_id}:agent-a").kernel_session_id == "sess-2"

    assert first_relay["payload"]["conversation_id"] == old_conversation_id
    assert old_after_relay["payload"]["conversation_id"] == old_conversation_id
    assert new_after_relay["payload"]["conversation_id"] == new_conversation_id
    assert first_relay["payload"]["agent_id"] == "agent-a"
    assert old_after_relay["payload"]["agent_id"] == "agent-a"
    assert new_after_relay["payload"]["agent_id"] == "agent-a"
    assert first_relay["payload"]["metadata"] == {
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 1,
        "system_prompt": "You are agent-a.",
    }
    assert old_after_relay["payload"]["metadata"] == {
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 1,
        "system_prompt": "You are agent-a.",
    }
    assert new_after_relay["payload"]["metadata"] == {
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 2,
        "system_prompt": "You are upgraded.",
    }

    assert relay_adapter.sent[0].target_chat_id == old_conversation_id
    assert relay_adapter.sent[1].target_chat_id == old_conversation_id
    assert relay_adapter.sent[2].target_chat_id == new_conversation_id
    assert relay_adapter.sent[0].metadata == {
        "relay_task_id": first_relay["payload"]["relay_task_id"],
        "idempotency_key": "idem-m150-old-before",
        "message_id": first_relay["payload"]["message"]["id"],
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 1,
        "system_prompt": "You are agent-a.",
    }
    assert relay_adapter.sent[1].metadata == {
        "relay_task_id": old_after_relay["payload"]["relay_task_id"],
        "idempotency_key": "idem-m150-old-after",
        "message_id": old_after_relay["payload"]["message"]["id"],
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 1,
        "system_prompt": "You are agent-a.",
    }
    assert relay_adapter.sent[2].metadata == {
        "relay_task_id": new_after_relay["payload"]["relay_task_id"],
        "idempotency_key": "idem-m150-new-after",
        "message_id": new_after_relay["payload"]["message"]["id"],
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 2,
        "system_prompt": "You are upgraded.",
    }
    assert relay_adapter.sent[1].text == "gateway-reply:hello after sync old"
    assert relay_adapter.sent[2].text == "gateway-reply:hello after sync new"

    assert len(old_completed_payloads) == 2
    assert len(new_completed_payloads) == 1
    assert old_completed_payloads[0]["relay_metadata"] == first_relay["payload"]["metadata"]
    assert old_completed_payloads[1]["relay_metadata"] == old_after_relay["payload"]["metadata"]
    assert new_completed_payloads[0]["relay_metadata"] == new_after_relay["payload"]["metadata"]
    assert old_completed_payloads[1]["agent_id"] == "agent-a"
    assert new_completed_payloads[0]["agent_id"] == "agent-a"
    assert old_completed_payloads[1]["idempotency_key"] == "idem-m150-old-after"
    assert new_completed_payloads[0]["idempotency_key"] == "idem-m150-new-after"

    assert sync_frame == {
        "type": "config.sync",
        "payload": {"agent_id": "agent-a", "profile_version": 2},
    }
    assert patched.json()["profile_version"] == 2
    assert patched.json()["system_prompt"] == "You are upgraded."
    assert current.json()["profile_version"] == 1
    assert current.json()["system_prompt"] == "You are agent-a."
    assert old_before.json()["conversation_id"] == old_conversation_id
    assert old_after.json()["conversation_id"] == old_conversation_id
    assert new_after.json()["conversation_id"] == new_conversation_id
    assert sync.latest_profile_version("agent-a") == 2
    assert request.profile_version == 2
    assert request.agent_id == "agent-a"
