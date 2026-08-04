"""Integration coverage for terminal external Agent snapshot reconciliation."""

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.agents import AgentProfileRepository

from .conftest import authorize, register_user, seed_user_under_owner


def _external_conversation(client: TestClient, app) -> tuple[str, str]:
    owner = register_user(client, username="owner")
    authorize(client, owner)
    agent_user_id = seed_user_under_owner(
        client, username="agent:plato", owner_id=owner.owner_id
    )
    AgentProfileRepository(app.state.connection).upsert_profile(
        agent_id="plato",
        owner_id=owner.owner_id,
        display_name="Plato",
        description="",
        system_prompt="You are Plato.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root="",
    )
    response = client.post(
        "/im/v1/conversations/external/find-or-create",
        json={
            "external_source": "feishu",
            "external_chat_id": "chat-1",
            "agent_id": "plato",
            "title": "Plato · feishu",
            "is_group": False,
            "participant_ids": [f"user:{owner.id}", "agent:plato"],
            "metadata": {},
        },
    )
    assert response.status_code == 201, response.text
    assert agent_user_id
    return response.json()["id"], owner.id


def _snapshot() -> dict:
    return {
        "agent_id": "plato",
        "content": "complete answer",
        "thinking": [{"seq": 0, "text": "inspect"}],
        "tool_calls": [
            {
                "id": "call-1",
                "name": "read",
                "status": "completed",
                "input": {"path": "a.py"},
                "output": "ok",
                "duration_ms": 21,
                "seq": 1,
            }
        ],
        "token_usage": {
            "output": 2,
            "context_used": 10,
            "context_window": 100,
            "total": 12,
        },
        "elapsed_ms": 432,
        "delivery_status": "completed",
        "kernel_message_id": "kernel-1",
    }


def test_offline_snapshot_creates_one_complete_terminal_message_and_replays(
    tmp_path: Path,
) -> None:
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        conversation_id, owner_id = _external_conversation(client, app)
        anchor = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            headers={"Idempotency-Key": "shadow-user-1"},
            json={
                "sender_user_id": owner_id,
                "content": "hello",
                "suppress_relay": True,
            },
        )
        assert anchor.status_code == 201, anchor.text
        url = (
            f"/im/v1/conversations/{conversation_id}/external-agent-messages/"
            "shadow-message-1"
        )

        first = client.put(url, json=_snapshot())
        replay = client.put(url, json=_snapshot())

        assert first.status_code == 200, first.text
        assert replay.status_code == 200, replay.text
        assert replay.json()["id"] == first.json()["id"]
        assert replay.json() == first.json()
        listed = client.get(f"/im/v1/conversations/{conversation_id}/messages").json()[
            "items"
        ]
        messages = [item["message"] for item in listed if item["type"] == "message"]
        assert len(messages) == 2
        assert messages[-1] == first.json()
        rows = app.state.connection.execute(
            """
            SELECT payload_json FROM conversation_events
            WHERE conversation_id = ? AND event_type = 'message.reconciled'
            ORDER BY event_id
            """,
            (conversation_id,),
        ).fetchall()
        payload = json.loads(rows[-1]["payload_json"])
        assert payload["message_id"] == first.json()["id"]
        assert "id" not in payload
        assert payload["thinking"] == [{"seq": 0, "text": "inspect"}]
        assert payload["tool_calls"][0]["seq"] == 1
        assert payload["elapsed_ms"] == 432


def test_snapshot_reconciles_existing_same_identity_without_moving_or_duplicating(
    tmp_path: Path,
) -> None:
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        conversation_id, _owner_id = _external_conversation(client, app)
        ack = asyncio.run(
            app.state.gateway_execution.handle_streaming_delta(
                payload={
                    "kind": "turn_start",
                    "conversation_id": conversation_id,
                    "agent_id": "plato",
                    "run_id": "run-live",
                    "shadow_message_id": "shadow-message-live",
                }
            )
        )
        live_message_id = ack["payload"]["message_id"]
        asyncio.run(
            app.state.gateway_execution.handle_streaming_delta(
                payload={
                    "kind": "message_delta",
                    "message_id": live_message_id,
                    "delta_text": "partial",
                    "run_id": "run-live",
                }
            )
        )
        listed = client.get(f"/im/v1/conversations/{conversation_id}/messages").json()[
            "items"
        ]
        live = next(item["message"] for item in listed if item["type"] == "message")
        created_at = live["created_at"]

        reconciled = client.put(
            f"/im/v1/conversations/{conversation_id}/external-agent-messages/"
            "shadow-message-live",
            json=_snapshot(),
        )

        assert reconciled.status_code == 200, reconciled.text
        assert reconciled.json()["id"] == live_message_id
        assert reconciled.json()["created_at"] == created_at
        assert reconciled.json()["content"] == "complete answer"
        assert reconciled.json()["thinking"] == [{"seq": 0, "text": "inspect"}]
        count = app.state.connection.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()[0]
        assert count == 1


def test_snapshot_rejects_non_shadow_conversation_and_non_terminal_status(
    tmp_path: Path,
) -> None:
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        authorize(client, owner)
        agent_user_id = seed_user_under_owner(
            client, username="agent:plato", owner_id=owner.owner_id
        )
        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "ordinary",
                "participant_ids": [owner.id, agent_user_id],
            },
        )
        assert conversation.status_code == 201
        url = (
            f"/im/v1/conversations/{conversation.json()['id']}/external-agent-messages/"
            "shadow-message-1"
        )

        ordinary = client.put(url, json=_snapshot())
        running_payload = {**_snapshot(), "delivery_status": "running"}
        running = client.put(url, json=running_payload)

        assert ordinary.status_code == 400
        assert running.status_code == 422
