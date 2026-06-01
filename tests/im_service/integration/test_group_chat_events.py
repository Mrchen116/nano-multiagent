"""Integration tests: per-agent SSE identity and distinct completion events for dual-mention group turns."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.application.event_service import EventService
from IM.app import create_app
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


def test_group_message_mentioning_two_agents_exposes_distinct_sse_identity_for_running_and_report_events(
    tmp_path: Path,
) -> None:
    """Backfill per-agent identity into SSE relay.processing/report events for one dual-mention turn."""

    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = make_agent_configs(tmp_path, "agent-q", "agent-a")
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((relay_adapter,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-q",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        user_id = seed_user(client, "alice")
        agent_q_user_id = seed_user(client, "agent:agent-q")
        agent_a_user_id = seed_user(client, "agent:agent-a")
        seed_node_and_profiles(app, agent_ids=("agent-q", "agent-a"))

        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Dual Mention SSE Identity",
                "participant_ids": [user_id, agent_q_user_id, agent_a_user_id],
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
                        "agents": ["agent-q", "agent-a"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            posted = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-dual-sse"},
                json={
                    "sender_user_id": user_id,
                    "content": "@agent-q @agent-a please review this rollout together",
                    "target_node_id": "node-1",
                },
            )
            assert posted.status_code == 201
            relay_frames = [websocket.receive_json(), websocket.receive_json()]
            relay_frame_by_agent = {
                frame["payload"]["agent_id"]: frame for frame in relay_frames
            }
            assert set(relay_frame_by_agent) == {"agent-q", "agent-a"}

            for agent_id, run_id in (("agent-q", "run-q"), ("agent-a", "run-a")):
                relay_payload = relay_frame_by_agent[agent_id]["payload"]
                send_delivery_receipt(
                    websocket,
                    relay_payload=relay_payload,
                    delivery_status="sent",
                    detail=f"run_id={run_id}",
                )
                websocket.send_json(
                    {
                        "type": "node.report",
                        "payload": {
                            "node_id": "node-1",
                            "run_id": run_id,
                            "status": "running",
                            "agent_id": agent_id,
                            "conversation_id": conversation_id,
                            "message_id": relay_payload["message"]["id"],
                            "summary": f"{agent_id} is preparing a summary",
                        },
                    }
                )
                assert websocket.receive_json() == {
                    "type": "ack",
                    "payload": {"message_type": "node.report", "node_id": "node-1"},
                }
                websocket.send_json(
                    {
                        "type": "node.report",
                        "payload": {
                            "node_id": "node-1",
                            "run_id": run_id,
                            "status": "completed",
                            "agent_id": agent_id,
                            "conversation_id": conversation_id,
                            "message_id": relay_payload["message"]["id"],
                            "summary": f"{agent_id} finished the review",
                        },
                    }
                )
                assert websocket.receive_json() == {
                    "type": "ack",
                    "payload": {"message_type": "node.report", "node_id": "node-1"},
                }

        event_service = EventService(events=client.app.state.event_repository)
        enriched = event_service.list_events(
            conversation_id=conversation_id, after_event_id=0, limit=200
        )
        sse_events = [
            (ev.event_type, json.loads(ev.payload_json))
            for ev in enriched
            if ev.event_type in ("relay.processing", "relay.report")
        ]

    processing_payloads = [
        payload
        for event_type, payload in sse_events
        if event_type == "relay.processing"
    ]
    report_payloads = [
        payload for event_type, payload in sse_events if event_type == "relay.report"
    ]
    assert {payload["agent_id"] for payload in processing_payloads} == {
        "agent-q",
        "agent-a",
    }
    assert {payload["relay_task_id"] for payload in processing_payloads} == {
        relay_frame_by_agent["agent-q"]["payload"]["relay_task_id"],
        relay_frame_by_agent["agent-a"]["payload"]["relay_task_id"],
    }
    assert {payload["agent_id"] for payload in report_payloads} == {
        "agent-q",
        "agent-a",
    }
    assert {payload["relay_task_id"] for payload in report_payloads} == {
        relay_frame_by_agent["agent-q"]["payload"]["relay_task_id"],
        relay_frame_by_agent["agent-a"]["payload"]["relay_task_id"],
    }


def test_group_message_mentioning_two_agents_persists_distinct_completion_events(
    tmp_path: Path,
) -> None:
    """Keep per-agent receipt identity distinct when one group message mentions two agents."""

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
                "title": "Dual Mention Group",
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
                headers={"Idempotency-Key": "idem-group-dual"},
                json={
                    "sender_user_id": user_id,
                    "content": "@agent-a @agent-b please review this rollout together",
                    "target_node_id": "node-1",
                },
            )
            assert posted.status_code == 201
            relay_frames = [websocket.receive_json(), websocket.receive_json()]
            relay_frame_by_agent = {
                frame["payload"]["agent_id"]: frame for frame in relay_frames
            }
            assert set(relay_frame_by_agent) == {"agent-a", "agent-b"}

            relay_adapter.accept_relay(relay_frame_by_agent["agent-a"]["payload"])
            relay_adapter.accept_relay(relay_frame_by_agent["agent-b"]["payload"])

            for agent_id in ("agent-a", "agent-b"):
                relay_payload = relay_frame_by_agent[agent_id]["payload"]
                sent_ack = send_delivery_receipt(
                    websocket,
                    relay_payload=relay_payload,
                    delivery_status="sent",
                    detail=f"run_id={agent_id}",
                )
                completed_ack = send_delivery_receipt(
                    websocket,
                    relay_payload=relay_payload,
                    delivery_status="completed",
                    detail=f"reply from {agent_id}",
                )
                assert sent_ack["type"] == "ack"
                assert completed_ack["type"] == "ack"

        event_rows = app.state.connection.execute(
            """
            SELECT event_type, payload_json
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (conversation_id,),
        ).fetchall()

    completed_payloads = [
        json.loads(row["payload_json"])
        for row in event_rows
        if row["event_type"] == "relay.completed"
    ]
    delivered_payloads = [
        json.loads(row["payload_json"])
        for row in event_rows
        if row["event_type"] == "message.delivered"
    ]
    assert [call["text"] for call in kernel_client.send_calls] == [
        "[Alice] @agent-a @agent-b please review this rollout together",
        "[Alice] @agent-a @agent-b please review this rollout together",
    ]
    assert {payload["agent_id"] for payload in completed_payloads} == {
        "agent-a",
        "agent-b",
    }
    assert {payload["relay_task_id"] for payload in completed_payloads} == {
        relay_frame_by_agent["agent-a"]["payload"]["relay_task_id"],
        relay_frame_by_agent["agent-b"]["payload"]["relay_task_id"],
    }
    assert [
        payload["detail"]
        for payload in sorted(
            completed_payloads, key=lambda payload: payload["agent_id"]
        )
    ] == [
        "reply from agent-a",
        "reply from agent-b",
    ]
    assert {payload["agent_id"] for payload in delivered_payloads} == {
        "agent-a",
        "agent-b",
    }
    assert {payload["relay_task_id"] for payload in delivered_payloads} == {
        relay_frame_by_agent["agent-a"]["payload"]["relay_task_id"],
        relay_frame_by_agent["agent-b"]["payload"]["relay_task_id"],
    }
