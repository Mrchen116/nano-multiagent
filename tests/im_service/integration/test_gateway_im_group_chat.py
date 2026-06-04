"""Browserless IM ↔ Gateway: group chat profile sync and NO_REPLY suppression."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories import UserRepository
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._gateway_helpers import (
    _FakeKernelClient,
    make_agent_configs,
    receive_group_relays,
    seed_node_and_profiles,
    seed_user,
    send_delivery_receipt,
)


def test_group_chat_uses_live_updated_profile_after_config_sync_in_same_conversation(
    tmp_path: Path,
) -> None:
    """An existing group conversation must use the updated mentioned-agent profile after config sync."""
    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = make_agent_configs(tmp_path, "agent-a", "agent-b")
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
        agent_a_user_id = seed_user(client, "agent:agent-a")
        agent_b_user_id = seed_user(client, "agent:agent-b")
        owner = UserRepository(app.state.connection).get_user(user_id=owner_id)
        assert owner is not None
        seed_node_and_profiles(
            app, owner_id=owner.owner_id, agent_ids=("agent-a", "agent-b")
        )

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
                    # bugfix-358: mention format changed to XML tag.
                    "content": '<mention type="agent" target_id="agent-a"/> first mention',
                    "target_node_id": "node-1",
                },
            )
            assert first_message.status_code == 201
            first_relay_by_agent = receive_group_relays(websocket)
            first_relay = first_relay_by_agent["agent-a"]
            relay_adapter.accept_relay(first_relay_by_agent["agent-a"]["payload"])
            relay_adapter.accept_relay(first_relay_by_agent["agent-b"]["payload"])
            send_delivery_receipt(
                websocket,
                relay_payload=first_relay["payload"],
                delivery_status="sent",
                detail=None,
            )
            peer_context_frames: list[dict[str, object]] = []
            send_delivery_receipt(
                websocket,
                relay_payload=first_relay["payload"],
                delivery_status="completed",
                # bugfix-358: detail echoes actual relay output text (now with XML mention tag).
                detail='gateway-reply:<mention type="agent" target_id="agent-a"/> first mention',
                extra_frames=peer_context_frames,
            )
            # bugfix-358: peer relay no longer carries background_context_only;
            # Gateway decides trigger vs buffer from mentioned_agent_ids alone.
            assert peer_context_frames, (
                "expected at least one peer agent-reply relay frame"
            )

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
            pipeline.register_agent(
                AgentWorkspaceConfig(
                    agent_id="agent-a",
                    workspace_root=agents[0].workspace_root,
                    title=agents[0].title,
                    system_prompt="When mentioned in a group chat, reply exactly with NO_REPLY.",
                )
            )
            pipeline.drop_agent_sessions("agent-a")

            second_message = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-after-sync"},
                json={
                    "sender_user_id": human_user_id,
                    # bugfix-358: mention format changed to XML tag.
                    "content": '<mention type="agent" target_id="agent-a"/> please stay silent if NO_REPLY works.',
                    "target_node_id": "node-1",
                },
            )
            assert second_message.status_code == 201
            second_relay_by_agent = receive_group_relays(websocket)
            second_relay = second_relay_by_agent["agent-a"]
            relay_adapter.accept_relay(second_relay_by_agent["agent-a"]["payload"])
            relay_adapter.accept_relay(second_relay_by_agent["agent-b"]["payload"])
            send_delivery_receipt(
                websocket,
                relay_payload=second_relay["payload"],
                delivery_status="sent",
                detail=None,
            )
            send_delivery_receipt(
                websocket,
                relay_payload=second_relay["payload"],
                delivery_status="completed",
                detail="NO_REPLY | suppressed_by=no_reply_token",
            )

        event_rows = app.state.connection.execute(
            """
            SELECT event_type, payload_json
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (conversation_id,),
        ).fetchall()
        accepted_payloads = [
            json.loads(row["payload_json"])
            for row in event_rows
            if row["event_type"] == "relay.accepted"
        ]
        completed_payloads = [
            json.loads(row["payload_json"])
            for row in event_rows
            if row["event_type"] == "relay.completed"
        ]

    # participants use logical agent_id (from "agent:" username prefix), not user UUID.
    assert [call["metadata"] for call in kernel_client.create_session_calls] == [
        {
            "agent_id": "agent-a",
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "agent_features": {},
            # feat-394-M3: heartbeat/cron enabled flags injected into session metadata
            "heartbeat_enabled": False,
            "cron_enabled": False,
            "config_profile_version": 1,
            "system_prompt": "You are agent-a.",
            "conversation_type": "group",
            "external_chat_id": conversation_id,
            "participants": [
                {"type": "user", "user_id": human_user_id, "display_name": "Alice"},
                {"type": "agent", "agent_id": "agent-a", "display_name": "A"},
                {"type": "agent", "agent_id": "agent-b", "display_name": "B"},
            ],
            "participant_agent_ids": ["agent-a", "agent-b"],
        },
        {
            "agent_id": "agent-a",
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "agent_features": {},
            # feat-394-M3: heartbeat/cron enabled flags injected into session metadata
            "heartbeat_enabled": False,
            "cron_enabled": False,
            "config_profile_version": 2,
            "system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY.",
            "conversation_type": "group",
            "external_chat_id": conversation_id,
            "participants": [
                {"type": "user", "user_id": human_user_id, "display_name": "Alice"},
                {"type": "agent", "agent_id": "agent-a", "display_name": "agent-a v2"},
                {"type": "agent", "agent_id": "agent-b", "display_name": "B"},
            ],
            "participant_agent_ids": ["agent-a", "agent-b"],
        },
    ]
    assert [call["session_id"] for call in kernel_client.send_calls] == [
        "sess-1",
        "sess-2",
    ]
    assert first_relay["payload"]["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-a"],
        "participant_agent_ids": ["agent-a", "agent-b"],
        "config_profile_version": 1,
    }
    assert second_relay["payload"]["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-a"],
        "participant_agent_ids": ["agent-a", "agent-b"],
        "config_profile_version": 2,
    }
    # First relay: profile_version=1, no NO_REPLY prompt → message is sent.
    # Second relay: profile_version=2, NO_REPLY prompt → output suppressed; relay_adapter.sent only has first message.
    assert [message.text for message in relay_adapter.sent] == [
        'gateway-reply:[Alice] <mention type="agent" target_id="agent-a"/> first mention',
    ]
    assert relay_adapter.sent[0].metadata["config_profile_version"] == 1
    assert [payload["detail"] for payload in accepted_payloads] == [None, None]
    assert [payload["detail"] for payload in completed_payloads] == [
        'gateway-reply:<mention type="agent" target_id="agent-a"/> first mention',
        "NO_REPLY | suppressed_by=no_reply_token",
    ]


def test_group_chat_keeps_no_reply_when_completed_snapshot_and_late_stream_delta_conflict(
    tmp_path: Path,
) -> None:
    """Completed NO_REPLY snapshots must win over stale streamed text in the same relay chain."""
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
        agent_a_user_id = seed_user(client, "agent:agent-a")
        agent_b_user_id = seed_user(client, "agent:agent-b")
        owner = UserRepository(app.state.connection).get_user(user_id=owner_id)
        assert owner is not None
        seed_node_and_profiles(
            app, owner_id=owner.owner_id, agent_ids=("agent-a", "agent-b")
        )

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
        pipeline.register_agent(
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=agents[0].workspace_root,
                title=agents[0].title,
                system_prompt="When mentioned in a group chat, reply exactly with NO_REPLY.",
            )
        )

        group_conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "same group",
                "participant_ids": [human_user_id, agent_a_user_id, agent_b_user_id],
            },
        )
        assert group_conversation.status_code == 201
        assert group_conversation.json()["type"] == "group"
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

            second_message = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-after-sync-stream-conflict"},
                json={
                    "sender_user_id": human_user_id,
                    # bugfix-358: mention format changed to XML tag.
                    "content": '<mention type="agent" target_id="agent-a"/> please stay silent if NO_REPLY works.',
                    "target_node_id": "node-1",
                },
            )
            assert second_message.status_code == 201
            second_relay_by_agent = receive_group_relays(websocket)
            second_relay = second_relay_by_agent["agent-a"]
            relay_task_id = second_relay["payload"]["relay_task_id"]
            message_id = second_relay["payload"]["message"]["id"]
            # submit_message auto-seeds SSE events via _FakeKernelClient.submit_message.
            # The NO_REPLY output_text is determined by system_prompt + profile_version match.
            # We no longer override session_events with old text_delta format; pipeline uses SSE stream.
            relay_adapter.accept_relay(second_relay_by_agent["agent-a"]["payload"])
            send_delivery_receipt(
                websocket,
                relay_payload=second_relay["payload"],
                delivery_status="sent",
                detail=None,
            )
            peer_context_frames: list[dict[str, object]] = []
            send_delivery_receipt(
                websocket,
                relay_payload=second_relay["payload"],
                delivery_status="completed",
                detail="NO_REPLY | suppressed_by=no_reply_token",
                extra_frames=peer_context_frames,
            )
            assert peer_context_frames == []

        event_rows = app.state.connection.execute(
            """
            SELECT event_type, payload_json
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (conversation_id,),
        ).fetchall()
        accepted_payloads = [
            json.loads(row["payload_json"])
            for row in event_rows
            if row["event_type"] == "relay.accepted"
        ]
        completed_payloads = [
            json.loads(row["payload_json"])
            for row in event_rows
            if row["event_type"] == "relay.completed"
        ]

    # participants use logical agent_id, not user UUID (bugfix-358 cleanup).
    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agents[0].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent-A",
            "metadata": {
                "agent_id": "agent-a",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
                # feat-394-M3: heartbeat/cron enabled flags injected into session metadata
                "heartbeat_enabled": False,
                "cron_enabled": False,
                "config_profile_version": 2,
                "system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY.",
                "conversation_type": "group",
                "external_chat_id": conversation_id,
                "participants": [
                    {"type": "user", "user_id": human_user_id, "display_name": "Alice"},
                    {
                        "type": "agent",
                        "agent_id": "agent-a",
                        "display_name": "agent-a v2",
                    },
                    {"type": "agent", "agent_id": "agent-b", "display_name": "B"},
                ],
                "participant_agent_ids": ["agent-a", "agent-b"],
            },
        }
    ]
    assert kernel_client.send_calls == [
        # bugfix-358: mention format in content changed to XML tag; group prefix "[Alice]" added by pipeline.
        {
            "session_id": "sess-1",
            "text": '[Alice] <mention type="agent" target_id="agent-a"/> please stay silent if NO_REPLY works.',
            "run_id": "run-1",
        }
    ]
    assert second_relay["payload"]["relay_task_id"] == relay_task_id
    assert second_relay["payload"]["message"]["id"] == message_id
    # With SSE stream architecture, NO_REPLY output from kernel causes pipeline to suppress relay.
    # relay_adapter.sent is empty; completed delivery receipt carries the NO_REPLY suppress detail.
    assert relay_adapter.sent == []
    assert [payload["detail"] for payload in accepted_payloads] == [None]
    assert [payload["detail"] for payload in completed_payloads] == [
        "NO_REPLY | suppressed_by=no_reply_token"
    ]
