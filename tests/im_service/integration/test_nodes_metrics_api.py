"""Integration tests for IM node board and usage metrics APIs."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories import NodeRepository


def _create_user(client: TestClient, username: str) -> str:
    response = client.post(
        "/im/v1/users",
        json={"username": username, "display_name": username.title()},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_conversation(client: TestClient, participant_id: str) -> str:
    response = client.post(
        "/im/v1/conversations",
        json={"title": "chat", "participant_ids": [participant_id]},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_nodes_list_and_config_update(tmp_path: Path) -> None:
    """List nodes and update node center-config fields."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        repo = NodeRepository(app.state.connection)
        repo.upsert_node(node_id="node-1", node_name="MacBook", status="online", version="1.0.0")

        listed = client.get("/im/v1/nodes")
        assert listed.status_code == 200
        assert listed.json() == [
            {
                "node_id": "node-1",
                "owner_id": "",
                "node_name": "MacBook",
                "status": "online",
                "last_heartbeat_at": "",
                "agent_count": 0,
                "version": "1.0.0",
                "relay_enabled": True,
                "reporting_enabled": True,
                "alias": None,
                "last_error": None,
            }
        ]

        updated = client.patch(
            "/im/v1/nodes/node-1/config",
            json={"alias": "Office Mac", "relay_enabled": False, "reporting_enabled": True},
        )
        assert updated.status_code == 200
        assert updated.json()["alias"] == "Office Mac"
        assert updated.json()["relay_enabled"] is False
        assert updated.json()["reporting_enabled"] is True


def test_usage_metrics_aggregate_messages_by_scope(tmp_path: Path) -> None:
    """Aggregate token and turn usage for user and agent messages."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)

        agent_create = client.post(
            "/im/v1/users",
            json={"username": "agent-alpha", "display_name": "Agent Alpha"},
        )
        assert agent_create.status_code == 201
        agent_id = agent_create.json()["id"]
        app.state.connection.execute(
            "INSERT INTO conversation_participants(conversation_id, user_id) VALUES (?, ?)",
            (conversation_id, agent_id),
        )
        app.state.connection.commit()

        created_user_message = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "hello there world"},
        )
        assert created_user_message.status_code == 201

        created_agent_message = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": agent_id, "sender_type": "agent", "content": "reply from agent"},
        )
        assert created_agent_message.status_code == 201

        metrics = client.get(f"/im/v1/metrics/usage?conversation_id={conversation_id}")
        assert metrics.status_code == 200
        payload = metrics.json()
        assert len(payload) == 2
        owner_row = next(item for item in payload if item["scope"] == "conversation")
        agent_row = next(item for item in payload if item["scope"] == "agent")
        assert owner_row["turns"] == 1
        assert owner_row["prompt_tokens"] == 3
        assert owner_row["completion_tokens"] == 0
        assert owner_row["total_tokens"] == 3
        assert owner_row["conversation_id"] == conversation_id
        assert owner_row["agent_id"] is None
        assert agent_row["turns"] == 1
        assert agent_row["prompt_tokens"] == 3
        assert agent_row["completion_tokens"] == 3
        assert agent_row["total_tokens"] == 6
        assert agent_row["agent_id"] == agent_id
