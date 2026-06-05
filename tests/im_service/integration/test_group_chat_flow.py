"""Group chat integration tests: no-reply suppression and explicit agent mention roundtrip."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from personal_assistant.channels.base import OutboundMessage
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._group_chat_helpers import (
    _FakeKernelClient,
    make_agent_configs,
    seed_node_and_profiles,
    seed_user,
    send_delivery_receipt,
)


def test_group_message_with_mention_and_no_reply_token_stays_silent(
    tmp_path: Path,
) -> None:
    """A mentioned group relay that returns NO_REPLY must complete without outbound chat text."""

    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    kernel_client.default_output_text = "NO_REPLY"
    relay_adapter = WebRelayAdapter()
    agents = make_agent_configs(tmp_path, "agent-a", "agent-b")
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((relay_adapter,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        user_id = seed_user(client, "alice")
        agent_a_user_id = seed_user(client, "agent:agent-a")
        agent_b_user_id = seed_user(client, "agent:agent-b")
        seed_node_and_profiles(app, agent_ids=("agent-a", "agent-b"))

        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Quiet Group",
                "participant_ids": [user_id, agent_a_user_id, agent_b_user_id],
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
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-a", "agent-b"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            posted = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-no-reply"},
                json={
                    "sender_user_id": user_id,
                    "content": "@agent-a stay quiet",
                    "target_node_id": "node-1",
                },
            )
            assert posted.status_code == 201
            relay_frames = [websocket.receive_json(), websocket.receive_json()]
            relay_frame_by_agent = {
                frame["payload"]["agent_id"]: frame for frame in relay_frames
            }
            relay_adapter.accept_relay(relay_frame_by_agent["agent-a"]["payload"])
            relay_adapter.accept_relay(relay_frame_by_agent["agent-b"]["payload"])
            sent_ack = send_delivery_receipt(
                websocket,
                relay_payload=relay_frame_by_agent["agent-a"]["payload"],
                delivery_status="sent",
                detail=None,
            )
            completed_ack = send_delivery_receipt(
                websocket,
                relay_payload=relay_frame_by_agent["agent-a"]["payload"],
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
    assert kernel_client.send_calls == [
        {
            "session_id": "sess-1",
            "text": "[Alice] @agent-a stay quiet",
            "run_id": "run-1",
        }
    ]
    assert relay_adapter.sent == []
    assert sent_ack["type"] == "ack"
    assert completed_ack["type"] == "ack"
    assert [payload["detail"] for payload in accepted_payloads] == [None]
    assert [payload["detail"] for payload in completed_payloads] == [
        "NO_REPLY | suppressed_by=no_reply_token"
    ]


def test_group_conversation_creation_and_explicit_agent_mentions_roundtrip(
    tmp_path: Path,
) -> None:
    """Create a real group conversation and keep typed plus picker mentions pinned to their addressed agents."""

    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = make_agent_configs(tmp_path, "agent-a", "agent-b")
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((relay_adapter,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        user_id = seed_user(client, "alice")
        agent_a_user_id = seed_user(client, "agent:agent-a")
        agent_b_user_id = seed_user(client, "agent:agent-b")
        seed_node_and_profiles(app, agent_ids=("agent-a", "agent-b"))

        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Kernel Ops Group",
                "participant_ids": [user_id, agent_a_user_id, agent_b_user_id],
            },
        )
        assert conversation.status_code == 201
        body = conversation.json()
        assert body["type"] == "group"
        conversation_id = body["id"]

        listed = client.get("/im/v1/conversations")
        assert listed.status_code == 200
        listed_items = listed.json()["items"]
        assert any(
            item["id"] == conversation_id and item["type"] == "group"
            for item in listed_items
        )

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

            first = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-a"},
                json={
                    "sender_user_id": user_id,
                    # bugfix-358: mention format changed to XML tag.
                    "content": '<mention type="agent" target_id="agent-a"/> please inspect rollout',
                    "target_node_id": "node-1",
                },
            )
            assert first.status_code == 201
            first_frames = [websocket.receive_json(), websocket.receive_json()]
            first_frame_by_agent = {
                frame["payload"]["agent_id"]: frame for frame in first_frames
            }
            relay_adapter.accept_relay(first_frame_by_agent["agent-a"]["payload"])
            relay_adapter.accept_relay(first_frame_by_agent["agent-b"]["payload"])

            second = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-b"},
                json={
                    "sender_user_id": user_id,
                    # bugfix-358: mention format changed to XML tag.
                    "content": '<mention type="agent" target_id="agent-b"/> review the result',
                    "target_node_id": "node-1",
                },
            )
            assert second.status_code == 201
            second_frames = [websocket.receive_json(), websocket.receive_json()]
            second_frame_by_agent = {
                frame["payload"]["agent_id"]: frame for frame in second_frames
            }
            relay_adapter.accept_relay(second_frame_by_agent["agent-a"]["payload"])
            relay_adapter.accept_relay(second_frame_by_agent["agent-b"]["payload"])

    first_frame = first_frame_by_agent["agent-a"]
    second_frame = second_frame_by_agent["agent-b"]
    assert [call["title"] for call in kernel_client.create_session_calls] == [
        "Agent-A",
        "Agent-B",
    ]
    # participants use logical agent_id (from "agent:" prefix), not user UUID.
    assert [call["metadata"] for call in kernel_client.create_session_calls] == [
        {
            "agent_id": "agent-a",
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "agent_features": {},
            "config_profile_version": 1,
            "conversation_type": "group",
            "participant_agent_ids": ["agent-a", "agent-b"],
            "external_chat_id": conversation_id,
            "participants": [
                {"type": "user", "user_id": user_id, "display_name": "Alice"},
                {"type": "agent", "agent_id": "agent-a", "display_name": "A"},
                {"type": "agent", "agent_id": "agent-b", "display_name": "B"},
            ],
        },
        {
            "agent_id": "agent-b",
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "agent_features": {},
            "config_profile_version": 1,
            "conversation_type": "group",
            "participant_agent_ids": ["agent-a", "agent-b"],
            "external_chat_id": conversation_id,
            "participants": [
                {"type": "user", "user_id": user_id, "display_name": "Alice"},
                {"type": "agent", "agent_id": "agent-a", "display_name": "A"},
                {"type": "agent", "agent_id": "agent-b", "display_name": "B"},
            ],
        },
    ]
    assert [call["text"] for call in kernel_client.send_calls] == [
        '[Alice] <mention type="agent" target_id="agent-a"/> please inspect rollout',
        '[Alice] <mention type="agent" target_id="agent-b"/> review the result',
    ]
    assert first_frame["payload"]["agent_id"] == "agent-a"
    assert first_frame["payload"]["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-a"],
        "participant_agent_ids": ["agent-a", "agent-b"],
        "config_profile_version": 1,
    }
    assert second_frame["payload"]["agent_id"] == "agent-b"
    assert second_frame["payload"]["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-b"],
        "participant_agent_ids": ["agent-a", "agent-b"],
        "config_profile_version": 1,
    }
    assert relay_adapter.sent == [
        OutboundMessage(
            channel_name="web_relay",
            text='reply:[Alice] <mention type="agent" target_id="agent-a"/> please inspect rollout',
            target_chat_id=conversation_id,
            thread_id=None,
            metadata={
                "relay_task_id": first_frame["payload"]["relay_task_id"],
                "idempotency_key": "idem-group-a:agent-a",
                "message_id": first_frame["payload"]["message"]["id"],
                "conversation_type": "group",
                "mentioned_agent_ids": ["agent-a"],
                "participant_agent_ids": ["agent-a", "agent-b"],
                "config_profile_version": 1,
                "sender_display_name": "Alice",
                "participants": [
                    {"user_id": user_id, "display_name": "Alice", "type": "user"},
                    {"agent_id": "agent-a", "display_name": "A", "type": "agent"},
                    {"agent_id": "agent-b", "display_name": "B", "type": "agent"},
                ],
            },
        ),
        OutboundMessage(
            channel_name="web_relay",
            text='reply:[Alice] <mention type="agent" target_id="agent-b"/> review the result',
            target_chat_id=conversation_id,
            thread_id=None,
            metadata={
                "relay_task_id": second_frame["payload"]["relay_task_id"],
                "idempotency_key": "idem-group-b:agent-b",
                "message_id": second_frame["payload"]["message"]["id"],
                "conversation_type": "group",
                "mentioned_agent_ids": ["agent-b"],
                "participant_agent_ids": ["agent-a", "agent-b"],
                "config_profile_version": 1,
                "sender_display_name": "Alice",
                "participants": [
                    {"user_id": user_id, "display_name": "Alice", "type": "user"},
                    {"agent_id": "agent-a", "display_name": "A", "type": "agent"},
                    {"agent_id": "agent-b", "display_name": "B", "type": "agent"},
                ],
            },
        ),
    ]
