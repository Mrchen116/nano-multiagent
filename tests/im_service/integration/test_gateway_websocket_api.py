"""Integration tests for IM gateway websocket and relay delivery."""

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.ws.gateway_handler import GatewayConnection

from .conftest import authorize, register_user, seed_user_under_owner


def _create_user(client: TestClient, username: str) -> str:
    """Auth-aware fixture: first call registers + authorizes, subsequent calls seed under tenant."""
    auth = client.headers.get("Authorization")
    if auth is None:
        user = register_user(client, username=username, display_name=username.title())
        authorize(client, user)
        return user.id
    me = client.get("/im/v1/me").json()
    return seed_user_under_owner(
        client, username=username, display_name=username.title(), owner_id=me["owner_id"]
    )


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
        viewer = register_user(client, username="viewer", display_name="Viewer")
        authorize(client, viewer)
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


def test_gateway_websocket_persists_completed_relay_chain_from_report_and_receipt(tmp_path: Path) -> None:
    """Persist relay processing/completed events even when report and receipt arrive after reconnect."""
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
            assert websocket.receive_json()["type"] == "ack"

            created = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-http-reconnect-chain"},
                json={
                    "sender_user_id": alice_id,
                    "content": "hello reconnect chain",
                    "target_node_id": "node-1",
                },
            )
            assert created.status_code == 201
            relay_frame = websocket.receive_json()
            relay_task_id = relay_frame["payload"]["relay_task_id"]
            message_id = relay_frame["payload"]["message"]["id"]

            websocket.send_json(
                {
                    "type": "node.delivery_receipt",
                    "payload": {
                        "node_id": "node-1",
                        "relay_task_id": relay_task_id,
                        "delivery_status": "sent",
                        "detail": "run_id=run-1",
                    },
                }
            )
            assert websocket.receive_json()["payload"]["status"] == "sent"

            websocket.send_json(
                {
                    "type": "node.report",
                    "payload": {
                        "node_id": "node-1",
                        "run_id": "run-1",
                        "status": "running",
                        "agent_id": "agent-a",
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "summary": "processing after reconnect",
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
                        "run_id": "run-1",
                        "status": "completed",
                        "agent_id": "agent-a",
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "summary": "completed after reconnect",
                    },
                }
            )
            assert websocket.receive_json() == {
                "type": "ack",
                "payload": {"message_type": "node.report", "node_id": "node-1"},
            }

            websocket.send_json(
                {
                    "type": "node.delivery_receipt",
                    "payload": {
                        "node_id": "node-1",
                        "relay_task_id": relay_task_id,
                        "delivery_status": "completed",
                        "detail": "completed after reconnect",
                    },
                }
            )
            assert websocket.receive_json() == {
                "type": "ack",
                "payload": {
                    "message_type": "node.delivery_receipt",
                    "node_id": "node-1",
                    "relay_task_id": relay_task_id,
                    "status": "completed",
                },
            }

        relay_row = app.state.connection.execute(
            "SELECT status, receipt_status, receipt_detail FROM relay_tasks WHERE relay_task_id = ?",
            (relay_task_id,),
        ).fetchone()
        event_rows = app.state.connection.execute(
            "SELECT event_type, delivery_status FROM conversation_events WHERE message_id = ? ORDER BY rowid ASC",
            (message_id,),
        ).fetchall()
        message_row = client.get(f"/im/v1/conversations/{conversation_id}/messages")

        assert relay_row is not None
        assert relay_row["status"] == "completed"
        assert relay_row["receipt_status"] == "completed"
        assert relay_row["receipt_detail"] == "completed after reconnect"
        assert [row["event_type"] for row in event_rows] == [
            "message.sent",
            "relay.accepted",
            "relay.processing",
            "relay.report",
            "relay.completed",
            "message.delivered",
        ]
        assert event_rows[-1]["delivery_status"] == "completed"
        assert message_row.status_code == 200
        assert message_row.json()["items"][-1]["delivery_status"] == "completed"


def test_gateway_websocket_exposes_actionable_last_error_in_node_board(tmp_path: Path) -> None:
    """Persist actionable startup guidance so `/im/v1/nodes` can surface it to operators."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        viewer = register_user(client, username="viewer", display_name="Viewer")
        authorize(client, viewer)
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {"node_id": "node-1", "node_name": "MacBook", "version": "1.0.0", "agents": ["agent-a"], "capabilities": {}},
                }
            )
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "node.heartbeat",
                    "payload": {
                        "node_id": "node-1",
                        "status": "online",
                        "agent_count": 1,
                        "last_error": "Gateway bootstrap failed. Next: open /im/v1/nodes and verify the node is visible.",
                    },
                }
            )
            websocket.receive_json()

            node_row = client.get("/im/v1/nodes")
            assert node_row.status_code == 200
            assert node_row.json()[0]["status"] == "degraded"
            assert node_row.json()[0]["last_error"] == (
                "Gateway bootstrap failed. Next: open /im/v1/nodes and verify the node is visible."
            )


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

        rows = client.app.state.connection.execute(
            """
            SELECT event_type, payload_json
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (conversation_id,),
        ).fetchall()
        types = [str(r["event_type"]) for r in rows]
        assert "relay.failed" in types
        assert "conversation.notice" in types
        payloads = [json.loads(str(r["payload_json"])) for r in rows]
        assert any(payload.get("progress_state") == "failed" for payload in payloads)
        assert any(payload.get("guidance") == "检查目标节点连接状态后重试，或切换到在线节点。" for payload in payloads)


def test_gateway_websocket_persists_heartbeat_report_into_conversation_events(tmp_path: Path) -> None:
    """Persist heartbeat-style node.report payloads into IM events users can read."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        agent_id = _create_user(client, "agent-a")
        conversation_id = client.post(
            "/im/v1/conversations",
            json={"title": "主 Agent · OpsBot", "participant_ids": [agent_id]},
        ).json()["id"]
        created = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": agent_id, "content": "heartbeat placeholder", "sender_type": "agent"},
        )
        assert created.status_code == 201
        message_id = created.json()["id"]

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "Gateway Node",
                        "version": "1.0.0",
                        "agents": ["agent-a"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            websocket.send_json(
                {
                    "type": "node.report",
                    "payload": {
                        "node_id": "node-1",
                        "run_id": "heartbeat-run-1",
                        "status": "completed",
                        "agent_id": "agent-a",
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "summary": "Heartbeat complete for main agent agent-a at 2026-03-13T09:00:00+00:00.",
                        "guidance": "Open your main agent thread in Web IM to review the latest heartbeat result.",
                    },
                }
            )
            report_ack = websocket.receive_json()

        assert report_ack == {"type": "ack", "payload": {"message_type": "node.report", "node_id": "node-1"}}
        bodies = client.app.state.connection.execute(
            "SELECT event_type, payload_json FROM conversation_events WHERE conversation_id = ? ORDER BY event_id DESC LIMIT 5",
            (conversation_id,),
        ).fetchall()
        joined = " ".join(str(b["event_type"]) + str(b["payload_json"]) for b in bodies)
        assert "relay.report" in joined
        assert "agent_run_completed" in joined
        assert "Open your main agent thread in Web IM to review the latest heartbeat result." in joined



def test_gateway_websocket_malformed_node_report_does_not_close_connection(tmp_path: Path) -> None:
    """IM 收到缺少 node_id 的畸形 node.report 时，返回 error ack 但 WS 连接继续存活。

    根因：`_handle_report` 中 `_require_text(payload.get("node_id"), ...)` 对畸形 payload
    会抛出异常；若异常冒泡出 dispatch 层则 WS 关闭。正确行为是捕获异常、返回 error 帧，
    连接本身不受影响——后续合法 heartbeat 仍然可以送达。
    """
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        agent_id = _create_user(client, "agent-b")
        conversation_id = _create_conversation(client, agent_id)
        created = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": agent_id, "content": "placeholder", "sender_type": "agent"},
        )
        assert created.status_code == 201
        message_id = created.json()["id"]

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json({
                "type": "node.register",
                "payload": {
                    "node_id": "node-1",
                    "node_name": "Gateway Node",
                    "version": "1.0.0",
                    "agents": ["agent-b"],
                    "capabilities": {"relay": True},
                },
            })
            assert websocket.receive_json()["type"] == "ack"

            # 畸形 node.report：缺少 node_id
            websocket.send_json({
                "type": "node.report",
                "payload": {
                    # node_id 故意缺失
                    "run_id": "heartbeat-bad-run",
                    "status": "completed",
                    "agent_id": "agent-b",
                    "conversation_id": "heartbeat:agent-b",
                    "message_id": "heartbeat-bad-run",
                    "summary": "malformed heartbeat report",
                },
            })
            bad_response = websocket.receive_json()
            # IM 应返回 error 帧（不应关闭连接）
            assert bad_response["type"] == "error"

            # 连接仍然存活：合法的 node.report 仍然可以送达
            websocket.send_json({
                "type": "node.report",
                "payload": {
                    "node_id": "node-1",
                    "run_id": "run-ok",
                    "status": "completed",
                    "agent_id": "agent-b",
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "summary": "connection still alive after malformed report",
                },
            })
            ok_ack = websocket.receive_json()
            assert ok_ack == {"type": "ack", "payload": {"message_type": "node.report", "node_id": "node-1"}}


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

        rows = client.app.state.connection.execute(
            "SELECT event_type FROM conversation_events WHERE conversation_id = ? ORDER BY event_id",
            (conversation_id,),
        ).fetchall()
        types = [str(r["event_type"]) for r in rows]
        assert "relay.failed" in types
        assert "conversation.notice" in types
