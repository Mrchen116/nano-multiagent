"""Integration tests for IM gateway websocket and relay delivery."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.ws.gateway_handler import GatewayConnection


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


class FailingGatewaySocket:
    async def send_json(self, payload: dict[str, object]) -> None:
        raise RuntimeError("socket closed")


async def _register_failing_gateway(app, *, node_id: str) -> None:  # noqa: ANN001
    await app.state.gateway_handler.handle_message(
        websocket=FailingGatewaySocket(),
        message_type="node.register",
        payload={
            "node_id": node_id,
            "node_name": node_id,
            "version": "1.0.0",
            "agents": ["agent-a"],
            "capabilities": {"relay": True},
        },
    )


async def _snapshot_gateway(app, *, node_id: str) -> GatewayConnection | None:  # noqa: ANN001
    return await app.state.gateway_handler.snapshot_connection(node_id=node_id)


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


def test_message_post_to_disconnected_node_persists_actionable_failure_events(tmp_path: Path) -> None:
    """Persist conversation-context failure feedback when the target node is offline."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)
        client.app.state.connection.execute(
            "INSERT INTO nodes(node_id, owner_id, node_name, status, last_heartbeat_at, agent_count, version, last_error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("node-1", None, "MacBook", "offline", "1970-01-01T00:00:00Z", 0, "", None),
        )
        client.app.state.connection.commit()

        created = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            headers={"Idempotency-Key": "idem-http-offline"},
            json={
                "sender_user_id": alice_id,
                "content": "hello gateway",
                "target_node_id": "node-1",
            },
        )
        assert created.status_code == 503
        assert created.json()["detail"] == "target_node_id is not connected"

        events = client.get(
            f"/im/v1/conversations/{conversation_id}/events?max_events=10&timeout_seconds=0.05"
        )
        assert events.status_code == 200
        parsed = [event for event in events.text.split("\n\n") if event.strip() and not event.startswith(":")]
        payloads = []
        for block in parsed:
            for line in block.splitlines():
                if line.startswith("data: "):
                    import json

                    payloads.append(json.loads(line[6:]))
        assert any("event: relay.failed" in block for block in parsed)
        assert any("event: conversation.notice" in block for block in parsed)
        assert any(payload.get("progress_state") == "failed" for payload in payloads)
        assert any(payload.get("guidance") == "检查目标节点连接状态后重试，或切换到在线节点。" for payload in payloads)


def test_message_post_with_broken_gateway_socket_returns_503_instead_of_500(tmp_path: Path) -> None:
    """Degrade broken websocket pushes into actionable 503 feedback instead of Internal Server Error."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)
        asyncio.run(_register_failing_gateway(app, node_id="node-1"))

        created = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            headers={"Idempotency-Key": "idem-http-broken-socket"},
            json={
                "sender_user_id": alice_id,
                "content": "hello broken gateway",
                "target_node_id": "node-1",
            },
        )

        assert created.status_code == 503
        assert created.json()["detail"] == "target_node_id is not connected"
        assert asyncio.run(_snapshot_gateway(app, node_id="node-1")) is None

        events = client.get(
            f"/im/v1/conversations/{conversation_id}/events?max_events=10&timeout_seconds=0.05"
        )
        assert events.status_code == 200
        assert "event: relay.failed" in events.text
        assert "event: conversation.notice" in events.text
