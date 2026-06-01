"""E2E: PA gateway register/heartbeat/disconnect → owner WS gets node.status_changed.

Validates feat-340-M10 决策 11 end-to-end: a real FastAPI app, two owner WS
connections (different tokens), one /im/ws/gateway connection from PA, and
assertion that node + agent status frames land only in the right owner's queue.
"""

from __future__ import annotations

import json
from pathlib import Path

from .conftest import authorize, make_app_client, register_user


def _bind_node_to_owner(client, *, node_id: str, owner_id: str) -> None:
    """Pre-seed a nodes row so the register path emits owner-scoped events."""
    connection = client.app.state.connection
    connection.execute(
        """
        INSERT INTO nodes(node_id, owner_id, node_name, status, last_heartbeat_at,
                          agent_count, version, relay_enabled, reporting_enabled,
                          alias, last_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node_id,
            owner_id,
            node_id,
            "offline",
            "1970-01-01T00:00:00Z",
            0,
            "",
            1,
            1,
            None,
            None,
        ),
    )
    connection.commit()


def _drain_until_pong(websocket, *, max_total: int = 20) -> list[dict]:
    """Send ping and collect event frames until the pong reply arrives.

    Forces an ordering barrier: the server processes the ping after all
    previously queued frames, so the pong marks the end of the broadcast batch.
    """
    websocket.send_text(json.dumps({"op": "ping"}))
    frames: list[dict] = []
    for _ in range(max_total):
        raw = websocket.receive_text()
        body = json.loads(raw)
        if body.get("op") == "pong":
            break
        if body.get("op") == "event":
            frames.append(body)
    return frames


def test_register_broadcasts_node_online_to_owner_via_real_ws(tmp_path: Path) -> None:
    """PA gateway sends node.register → matching owner's user WS receives node + agent online frames."""
    with make_app_client(tmp_path) as client:
        owner = register_user(client, username="owner-a")
        authorize(client, owner)
        _bind_node_to_owner(client, node_id="node-1", owner_id=owner.owner_id)

        with client.websocket_connect(
            f"/im/ws/user?token={owner.access_token}"
        ) as user_ws:
            # Skip the resume reply (an empty/initial frame may or may not arrive).
            user_ws.send_text(json.dumps({"op": "resume", "after_event_id": 0}))

            with client.websocket_connect("/im/ws/gateway") as gateway_ws:
                gateway_ws.send_text(
                    json.dumps(
                        {
                            "type": "node.register",
                            "payload": {
                                "node_id": "node-1",
                                "agents": ["agent-a"],
                                "capabilities": {},
                            },
                        }
                    )
                )
                # Read ack so we know the server fully processed register.
                ack = json.loads(gateway_ws.receive_text())
                assert ack["type"] == "ack"
                frames_online = _drain_until_pong(user_ws)

            # gateway_ws closing here triggers disconnect handler — drain offline frames.
            frames_offline = _drain_until_pong(user_ws)
            frames = frames_online + frames_offline

        event_types = [f["event_type"] for f in frames]
        # At least one node.status_changed online (from register) and one offline (from disconnect).
        node_frames = [f for f in frames if f["event_type"] == "node.status_changed"]
        agent_frames = [f for f in frames if f["event_type"] == "agent.status_changed"]
        assert any(f["data"]["status"] == "online" for f in node_frames), event_types
        assert any(f["data"]["status"] == "offline" for f in node_frames), event_types
        assert any(f["data"]["agent_id"] == "agent-a" for f in agent_frames), (
            event_types
        )


def test_cross_owner_isolation_real_ws(tmp_path: Path) -> None:
    """Owner B's WS must not see node events for owner A's node, even on the same app."""
    with make_app_client(tmp_path) as client:
        owner_a = register_user(client, username="owner-a")
        owner_b = register_user(client, username="owner-b")
        _bind_node_to_owner(client, node_id="node-a", owner_id=owner_a.owner_id)

        with client.websocket_connect(
            f"/im/ws/user?token={owner_a.access_token}"
        ) as ws_a:
            with client.websocket_connect(
                f"/im/ws/user?token={owner_b.access_token}"
            ) as ws_b:
                ws_a.send_text(json.dumps({"op": "resume", "after_event_id": 0}))
                ws_b.send_text(json.dumps({"op": "resume", "after_event_id": 0}))

                with client.websocket_connect("/im/ws/gateway") as gateway_ws:
                    gateway_ws.send_text(
                        json.dumps(
                            {
                                "type": "node.register",
                                "payload": {
                                    "node_id": "node-a",
                                    "agents": [],
                                    "capabilities": {},
                                },
                            }
                        )
                    )
                    json.loads(gateway_ws.receive_text())  # ack

                frames_a = _drain_until_pong(ws_a)
                # Use the same ping/pong barrier on ws_b. After draining, B should
                # have only the pong (no event frames before it).
                frames_b = _drain_until_pong(ws_b)

        assert any(f["event_type"] == "node.status_changed" for f in frames_a)
        assert frames_b == [], f"owner B must not see owner A's events, got {frames_b}"
