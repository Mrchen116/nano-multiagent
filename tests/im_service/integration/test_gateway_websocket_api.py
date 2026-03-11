"""Integration tests for IM gateway websocket and relay delivery."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


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


def test_gateway_websocket_registers_and_receives_relay_messages(tmp_path: Path) -> None:
    """Relay HTTP-created messages to a connected gateway websocket."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)

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
            register_ack = websocket.receive_json()
            assert register_ack == {
                "type": "ack",
                "payload": {"message_type": "node.register", "node_id": "node-1"},
            }

            created = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-http-1"},
                json={
                    "sender_user_id": alice_id,
                    "content": "hello gateway",
                    "target_node_id": "node-1",
                },
            )
            assert created.status_code == 201

            relay_frame = websocket.receive_json()
            assert relay_frame["type"] == "relay.message"
            assert relay_frame["payload"]["idempotency_key"] == "idem-http-1"
            assert relay_frame["payload"]["message"]["content"] == "hello gateway"
            relay_task_id = relay_frame["payload"]["relay_task_id"]

            websocket.send_json(
                {
                    "type": "node.delivery_receipt",
                    "payload": {
                        "node_id": "node-1",
                        "relay_task_id": relay_task_id,
                        "delivery_status": "completed",
                        "detail": "ok",
                    },
                }
            )
            receipt_ack = websocket.receive_json()
            assert receipt_ack == {
                "type": "ack",
                "payload": {
                    "message_type": "node.delivery_receipt",
                    "node_id": "node-1",
                    "relay_task_id": relay_task_id,
                    "status": "completed",
                },
            }


def test_gateway_websocket_receives_config_and_heartbeat_pushes(tmp_path: Path) -> None:
    """Push config.sync and heartbeat.trigger frames to connected nodes."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {"node_id": "node-1", "node_name": "MacBook", "version": "1.0.0", "agents": [], "capabilities": {}},
                }
            )
            websocket.receive_json()

            import asyncio

            pushed_config = asyncio.run(
                app.state.gateway_handler.push_config_sync(
                    target_node_id="node-1",
                    agent_id="agent-a",
                    profile_version=3,
                )
            )
            pushed_heartbeat = asyncio.run(
                app.state.gateway_handler.push_heartbeat_trigger(
                    target_node_id="node-1",
                    agent_id="agent-a",
                    reason="manual",
                )
            )

            assert pushed_config is True
            assert pushed_heartbeat is True
            assert websocket.receive_json() == {
                "type": "config.sync",
                "payload": {"agent_id": "agent-a", "profile_version": 3},
            }
            assert websocket.receive_json() == {
                "type": "heartbeat.trigger",
                "payload": {"agent_id": "agent-a", "reason": "manual"},
            }

            node_row = client.get("/im/v1/nodes")
            assert node_row.status_code == 200
            assert node_row.json()[0]["status"] == "online"
            assert node_row.json()[0]["node_name"] == "MacBook"
