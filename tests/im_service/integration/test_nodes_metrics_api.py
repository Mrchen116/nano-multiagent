"""Integration tests for IM node board and usage metrics APIs."""

from datetime import datetime, timedelta, timezone
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
                "status": "offline",
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


def test_nodes_list_marks_stale_and_disconnected_online_rows_as_offline(tmp_path: Path) -> None:
    """Show offline when stored online snapshots are stale or not live-connected."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        repo = NodeRepository(app.state.connection)
        stale_heartbeat = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        fresh_heartbeat = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        app.state.connection.execute(
            """
            INSERT INTO nodes(
                node_id,
                owner_id,
                node_name,
                status,
                last_heartbeat_at,
                agent_count,
                version,
                relay_enabled,
                reporting_enabled,
                alias,
                last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("node-stale", "", "Stale Node", "online", stale_heartbeat, 1, "1.0.0", 1, 1, None, None),
        )
        app.state.connection.execute(
            """
            INSERT INTO nodes(
                node_id,
                owner_id,
                node_name,
                status,
                last_heartbeat_at,
                agent_count,
                version,
                relay_enabled,
                reporting_enabled,
                alias,
                last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("node-fresh-but-disconnected", "", "Fresh Node", "online", fresh_heartbeat, 1, "1.0.1", 1, 1, None, None),
        )
        app.state.connection.commit()

        listed = client.get("/im/v1/nodes")
        assert listed.status_code == 200
        payload = {item["node_id"]: item for item in listed.json()}

        assert payload["node-stale"]["status"] == "offline"
        assert payload["node-fresh-but-disconnected"]["status"] == "offline"

        repo.record_gateway_registration(
            node_id="node-live",
            node_name="Live Node",
            version="2.0.0",
            agent_count=2,
        )
        listed_after_register = client.get("/im/v1/nodes")
        assert listed_after_register.status_code == 200
        payload_after_register = {item["node_id"]: item for item in listed_after_register.json()}
        assert payload_after_register["node-live"]["status"] == "offline"


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
        assert agent_row["prompt_tokens"] == 0
        assert agent_row["completion_tokens"] == 3
        assert agent_row["total_tokens"] == 3
        assert agent_row["agent_id"] == agent_id

        workspace_metrics = client.get(f"/im/v1/metrics/usage?owner_id={alice_id}")
        assert workspace_metrics.status_code == 200
        workspace_payload = workspace_metrics.json()
        assert any(item["scope"] == "owner" and item["total_tokens"] == 6 for item in workspace_payload)
        assert any(item["scope"] == "conversation" and item["conversation_id"] == conversation_id for item in workspace_payload)
        assert any(item["scope"] == "agent" and item["agent_id"] == agent_id for item in workspace_payload)


def test_usage_metrics_follow_real_relay_usage_by_owner_conversation_and_agent(tmp_path: Path) -> None:
    """Delay relay-backed usage until completed reports deliver real kernel usage."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner_id = _create_user(client, "alice")
        agent_id = _create_user(client, "agent-alpha")
        app.state.connection.execute("UPDATE users SET owner_id = ? WHERE id = ?", (owner_id, agent_id))
        app.state.connection.commit()
        conversation_id = client.post(
            "/im/v1/conversations",
            json={"title": "chat", "participant_ids": [owner_id, agent_id]},
        ).json()["id"]

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": [agent_id],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            created = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-real-usage"},
                json={
                    "sender_user_id": owner_id,
                    "content": "hello gateway",
                    "target_node_id": "node-1",
                },
            )
            assert created.status_code == 201
            relay_frame = websocket.receive_json()
            message_id = created.json()["id"]

            pre_report = client.get(f"/im/v1/metrics/usage?conversation_id={conversation_id}")
            assert pre_report.status_code == 200
            assert pre_report.json() == []

            websocket.send_json(
                {
                    "type": "node.report",
                    "payload": {
                        "node_id": "node-1",
                        "run_id": "run-1",
                        "status": "completed",
                        "agent_id": agent_id,
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            websocket.send_json(
                {
                    "type": "node.delivery_receipt",
                    "payload": {
                        "node_id": "node-1",
                        "relay_task_id": relay_frame["payload"]["relay_task_id"],
                        "delivery_status": "completed",
                        "detail": "ok",
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

        conversation_metrics = client.get(f"/im/v1/metrics/usage?conversation_id={conversation_id}")
        assert conversation_metrics.status_code == 200
        conversation_payload = conversation_metrics.json()
        assert len(conversation_payload) == 2
        conversation_row = next(item for item in conversation_payload if item["scope"] == "conversation")
        agent_row = next(item for item in conversation_payload if item["scope"] == "agent")
        assert conversation_row["prompt_tokens"] == 11
        assert conversation_row["completion_tokens"] == 7
        assert conversation_row["total_tokens"] == 18
        assert agent_row["agent_id"] == agent_id
        assert agent_row["total_tokens"] == 18

        workspace_metrics = client.get(f"/im/v1/metrics/usage?owner_id={owner_id}")
        assert workspace_metrics.status_code == 200
        workspace_payload = workspace_metrics.json()
        assert any(item["scope"] == "owner" and item["total_tokens"] == 18 for item in workspace_payload)
