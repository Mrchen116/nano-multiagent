"""Browserless IM ↔ Gateway: direct chat session lifecycle after config sync."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import UserRepository
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import AgentWorkspaceConfig
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


def test_direct_chat_recreates_legacy_kernel_session_without_workspace_metadata(
    tmp_path: Path,
) -> None:
    """Legacy direct bindings without workspace metadata must be refreshed before reuse."""
    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = make_agent_configs(tmp_path, "agent-a")
    registry = ChannelRegistry((relay_adapter,))
    session_store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=session_store,
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        owner_id = seed_user(client, "owner")
        human_user_id = seed_user(client, "alice")
        agent_user_id = seed_user(client, "agent:agent-a")
        owner = UserRepository(app.state.connection).get_user(user_id=owner_id)
        assert owner is not None
        seed_node_and_profiles(app, owner_id=owner.owner_id)

        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "legacy direct",
                "participant_ids": [human_user_id, agent_user_id],
            },
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]
        session_key = f"web_relay:{conversation_id}:agent-a"
        kernel_client.seed_session(
            session_id="sess-legacy",
            metadata={"agent_id": "agent-a", "config_profile_version": 1},
        )
        session_store.bind(
            session_key=session_key,
            kernel_session_id="sess-legacy",
            reply_context=type(
                "_ReplyContext",
                (),
                {
                    "channel_name": "web_relay",
                    "target_chat_id": conversation_id,
                    "thread_id": None,
                    "metadata": {},
                },
            )(),
        )

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

            message = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-legacy-workspace-refresh"},
                json={
                    "sender_user_id": human_user_id,
                    "content": "pwd一下",
                    "target_node_id": "node-1",
                },
            )
            assert message.status_code == 201
            relay_frame = websocket.receive_json()
            relay_adapter.accept_relay(relay_frame["payload"])
            websocket.send_json(
                {
                    "type": "node.delivery_receipt",
                    "payload": {
                        "node_id": "node-1",
                        "relay_task_id": relay_frame["payload"]["relay_task_id"],
                        "delivery_status": "completed",
                        "detail": "legacy-session-refreshed",
                    },
                }
            )
            receipt_ack = websocket.receive_json()
            assert receipt_ack == {
                "type": "ack",
                "payload": {
                    "message_type": "node.delivery_receipt",
                    "node_id": "node-1",
                    "relay_task_id": relay_frame["payload"]["relay_task_id"],
                    "status": "completed",
                },
            }

    assert [call["workspace_root"] for call in kernel_client.create_session_calls] == [
        str(agents[0].workspace_root)
    ]
    assert [call["session_id"] for call in kernel_client.send_calls] == ["sess-1"]
    assert session_store.get(session_key).kernel_session_id == "sess-1"


def test_direct_chat_keeps_old_session_after_config_sync_while_new_conversation_gets_new_profile(
    tmp_path: Path,
) -> None:
    """Old direct conversations stay pinned while new conversations pick up synced config."""
    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = make_agent_configs(tmp_path, "agent-a")
    registry = ChannelRegistry((relay_adapter,))
    session_store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=session_store,
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        owner_id = seed_user(client, "owner")
        human_user_id = seed_user(client, "alice")
        agent_user_id = seed_user(client, "agent:agent-a")
        owner = UserRepository(app.state.connection).get_user(user_id=owner_id)
        assert owner is not None
        seed_node_and_profiles(app, owner_id=owner.owner_id)

        old_conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "old direct",
                "participant_ids": [human_user_id, agent_user_id],
            },
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
                    system_prompt="You are upgraded.",
                    skills=("plan",),
                    tool_allowlist=("read",),
                    default_model="claude-sonnet-4",
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
                json={
                    "title": "new direct",
                    "participant_ids": [human_user_id, agent_user_id],
                },
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
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "agent_features": {},
            "config_profile_version": 1,
            "system_prompt": "You are agent-a.",
            "conversation_type": "direct",
        },
        {
            "agent_id": "agent-a",
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "agent_features": {},
            "config_profile_version": 1,
            "system_prompt": "You are upgraded.",
            "skills": ["plan"],
            "tool_allowlist": ["read"],
            "conversation_type": "direct",
        },
        {
            "agent_id": "agent-a",
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "agent_features": {},
            "config_profile_version": 2,
            "system_prompt": "You are upgraded.",
            "skills": ["plan"],
            "tool_allowlist": ["read"],
            "conversation_type": "direct",
        },
    ]
    assert [call["title"] for call in kernel_client.create_session_calls] == [
        "Agent-A",
        "agent-a v2",
        "agent-a v2",
    ]
    assert [call["workspace_root"] for call in kernel_client.create_session_calls] == [
        str(agents[0].workspace_root),
        str(tmp_path / "agent-a-refreshed"),
        str(tmp_path / "agent-a-refreshed"),
    ]
    assert [call["session_id"] for call in kernel_client.send_calls] == [
        "sess-1",
        "sess-2",
        "sess-3",
    ]
    assert (
        session_store.get(f"web_relay:{old_conversation_id}:agent-a").kernel_session_id
        == "sess-2"
    )
    assert (
        session_store.get(f"web_relay:{new_conversation_id}:agent-a").kernel_session_id
        == "sess-3"
    )

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
    }
    assert old_after_relay["payload"]["metadata"] == {
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 1,
    }
    assert new_after_relay["payload"]["metadata"] == {
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 2,
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
    }
    assert relay_adapter.sent[1].metadata == {
        "relay_task_id": old_after_relay["payload"]["relay_task_id"],
        "idempotency_key": "idem-m150-old-after",
        "message_id": old_after_relay["payload"]["message"]["id"],
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 1,
    }
    assert relay_adapter.sent[2].metadata == {
        "relay_task_id": new_after_relay["payload"]["relay_task_id"],
        "idempotency_key": "idem-m150-new-after",
        "message_id": new_after_relay["payload"]["message"]["id"],
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 2,
    }
    assert relay_adapter.sent[1].text == "gateway-reply:hello after sync old"
    assert relay_adapter.sent[2].text == "gateway-reply:hello after sync new"

    assert len(old_completed_payloads) == 2
    assert len(new_completed_payloads) == 1
    assert (
        old_completed_payloads[0]["relay_metadata"]
        == first_relay["payload"]["metadata"]
    )
    assert (
        old_completed_payloads[1]["relay_metadata"]
        == old_after_relay["payload"]["metadata"]
    )
    assert (
        new_completed_payloads[0]["relay_metadata"]
        == new_after_relay["payload"]["metadata"]
    )
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
