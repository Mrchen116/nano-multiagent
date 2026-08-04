"""Integration tests: per-agent SSE identity and distinct completion events for dual-mention group turns."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.application.event_service import EventService
from IM.app import create_app
from ._gateway_helpers import (
    seed_node_and_profiles,
    seed_user,
    send_delivery_receipt,
)


def test_dual_mention_keeps_per_agent_identity_across_realtime_and_completion_events(
    tmp_path: Path,
) -> None:
    """Keep each addressed agent identifiable through one dual-mention relay chain."""

    app = create_app(db_path=tmp_path / "im.db")
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
                send_delivery_receipt(
                    websocket,
                    relay_payload=relay_payload,
                    delivery_status="completed",
                    detail=f"reply from {agent_id}",
                )
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
            if ev.event_type
            in (
                "relay.processing",
                "relay.report",
                "relay.completed",
                "message.delivered",
            )
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
    for event_type in ("relay.completed", "message.delivered"):
        payloads = [payload for kind, payload in sse_events if kind == event_type]
        assert {payload["agent_id"] for payload in payloads} == {
            "agent-q",
            "agent-a",
        }
        assert {payload["relay_task_id"] for payload in payloads} == {
            relay_frame_by_agent["agent-q"]["payload"]["relay_task_id"],
            relay_frame_by_agent["agent-a"]["payload"]["relay_task_id"],
        }
