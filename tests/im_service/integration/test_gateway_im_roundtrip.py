"""Browserless IM ↔ Gateway: message roundtrip, device binding, and config sync."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories import UserRepository
from personal_assistant.channels.base import OutboundMessage
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._gateway_helpers import (
    _FakeKernelClient,
    make_agent_configs,
    seed_node_and_profiles,
    seed_user,
)


def test_web_im_message_roundtrip_browserless(tmp_path: Path) -> None:
    """Send a Web IM message through IM websocket, gateway pipeline, and reply channel."""
    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = make_agent_configs(tmp_path, "agent-a")
    registry = ChannelRegistry((relay_adapter,))
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        user_id = seed_user(client, "alice")
        agent_user_id = seed_user(client, "agent:agent-a")
        seed_node_and_profiles(app, agent_ids=("agent-a",))
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
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
                "config_profile_version": 1,
                "system_prompt": "You are agent-a.",
                "conversation_type": "direct",
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
            },
        )
    ]


def test_device_binding_end_to_end_updates_node_and_agent_owner(tmp_path: Path) -> None:
    """Bind one node to one user and propagate ownership to node-local agents."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner_id = seed_user(client, "owner", "Owner")
        seed_node_and_profiles(app, agent_ids=("agent-a", "agent-b"))

        start = client.post(
            "/im/v1/bind", json={"action": "start", "node_id": "node-1"}
        )
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
        owner_id = seed_user(client, "owner")
        seed_node_and_profiles(
            app,
            owner_id=UserRepository(app.state.connection)
            .get_user(user_id=owner_id)
            .owner_id,
        )
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
            live_read_request = websocket.receive_json()
            assert live_read_request["type"] == "agent.config.get"
            websocket.send_json(
                {
                    "type": "agent.config",
                    "payload": {
                        "request_id": live_read_request["payload"]["request_id"],
                        "agent_id": "agent-a",
                        "agent": None,
                    },
                }
            )
            assert websocket.receive_json() == {
                "type": "ack",
                "payload": {
                    "message_type": "agent.config",
                    "request_id": live_read_request["payload"]["request_id"],
                    "agent_id": "agent-a",
                },
            }
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


# ---------------------------------------------------------------------------
# Session reuse integration (W4 fix: stub gap)
# ---------------------------------------------------------------------------


def test_same_session_key_reuses_session_create_session_called_once(
    tmp_path: Path,
) -> None:
    """Two messages on the same session_key must trigger create_session exactly once.

    W4 regression (refactor-387): _FakeKernel.get_session lacked workspace_root at
    the top level, so _binding_matches_workspace_root always fell through and the
    session-reuse path was never exercised by integration tests.  After the fix,
    the stub returns the correct shape and this test validates that the pipeline
    reuses the session for the second message instead of creating a new one.
    """
    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = make_agent_configs(tmp_path, "agent-a")
    registry = ChannelRegistry((relay_adapter,))
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        user_id = seed_user(client, "alice")
        agent_user_id = seed_user(client, "agent:agent-a")
        seed_node_and_profiles(app, agent_ids=("agent-a",))
        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "session-reuse-chat",
                "participant_ids": [user_id, agent_user_id],
            },
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "test-node",
                        "version": "1.0.0",
                        "agents": ["agent-a"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            # First message — creates a new session.
            msg1 = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-session-reuse-1"},
                json={
                    "sender_user_id": user_id,
                    "content": "first message",
                    "target_node_id": "node-1",
                },
            )
            assert msg1.status_code == 201
            frame1 = websocket.receive_json()
            assert frame1["type"] == "relay.message"
            relay_adapter.accept_relay(frame1["payload"])

            # Second message in the same conversation (same session_key) — must reuse.
            msg2 = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-session-reuse-2"},
                json={
                    "sender_user_id": user_id,
                    "content": "second message",
                    "target_node_id": "node-1",
                },
            )
            assert msg2.status_code == 201
            frame2 = websocket.receive_json()
            assert frame2["type"] == "relay.message"
            relay_adapter.accept_relay(frame2["payload"])

    # create_session must have been called exactly once: second message reuses session.
    assert len(kernel_client.create_session_calls) == 1, (
        f"create_session must be called once for session reuse; "
        f"got {len(kernel_client.create_session_calls)} calls: {kernel_client.create_session_calls}"
    )
    assert len(kernel_client.send_calls) == 2, (
        f"both messages must have been dispatched to the kernel; "
        f"got {len(kernel_client.send_calls)} calls"
    )
    # Both messages must land in the same session.
    session_ids_used = {c["session_id"] for c in kernel_client.send_calls}
    assert len(session_ids_used) == 1, (
        f"both messages must use the same session_id, got: {session_ids_used}"
    )
