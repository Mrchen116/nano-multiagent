"""Browserless IM ↔ Gateway: node registration and agent label materialization."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app

from ._gateway_helpers import seed_node_and_profiles, seed_user


def test_gateway_registration_materializes_runtime_agents_before_and_after_bind(
    tmp_path: Path,
) -> None:
    """Gateway-advertised agents should be selectable in fresh runtime and reassigned after bind."""
    from tests.im_service._auth_helpers import authorize, register_user

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        authed = register_user(client, username="you", display_name="You")
        authorize(client, authed)

        # Shim so the rest of the test can still reference ``user.json()['id']`` etc.
        class _UserShim:
            status_code = 201

            def json(self):
                return {"id": authed.id, "owner_id": authed.owner_id}

        user = _UserShim()
        assert user.status_code == 201

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["Alpha", "Beta"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            before_bind = client.get("/im/v1/agents")
            assert before_bind.status_code == 200
            assert [item["agent_id"] for item in before_bind.json()] == [
                "Alpha",
                "Beta",
            ]
            assert [item["node_id"] for item in before_bind.json()] == [
                "node-1",
                "node-1",
            ]
            assert [item["owner_id"] for item in before_bind.json()] == ["", ""]
            assert [item["workspace_is_default"] for item in before_bind.json()] == [
                True,
                True,
            ]
            stored_rows = app.state.connection.execute(
                "SELECT agent_id, workspace_root FROM agent_profiles WHERE agent_id IN (?, ?) ORDER BY agent_id",
                ("Alpha", "Beta"),
            ).fetchall()
            assert [row["agent_id"] for row in stored_rows] == ["Alpha", "Beta"]
            assert [
                row["workspace_root"].endswith(
                    f"/nano-assistant/workspace/{row['agent_id']}"
                )
                for row in stored_rows
            ] == [True, True]

            bind_start = client.post(
                "/im/v1/bind", json={"action": "start", "node_id": "node-1"}
            )
            assert bind_start.status_code == 201
            bind_confirm = client.post(
                "/im/v1/bind",
                json={
                    "action": "confirm",
                    "bind_id": bind_start.json()["bind_id"],
                },
            )
            assert bind_confirm.status_code == 201

            listed = client.get("/im/v1/agents")
            assert listed.status_code == 200
            assert [item["agent_id"] for item in listed.json()] == ["Alpha", "Beta"]
            assert [item["node_id"] for item in listed.json()] == ["node-1", "node-1"]
            assert [item["owner_id"] for item in listed.json()] == [
                user.json()["owner_id"],
                user.json()["owner_id"],
            ]


def test_gateway_reregistration_preserves_canonical_agent_labels_after_restart(
    tmp_path: Path,
) -> None:
    """Fresh re-registration should rebuild canonical agent labels instead of leaving raw ids in the picker."""
    from tests.im_service._auth_helpers import authorize, register_user

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        viewer = register_user(client, username="viewer", display_name="Viewer")
        authorize(client, viewer)
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-m170-alpha", "agent-m170-beta"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

        first_listing = client.get("/im/v1/agents")
        assert first_listing.status_code == 200
        assert [item["display_name"] for item in first_listing.json()] == [
            "M170 Alpha",
            "M170 Beta",
        ]

        app.state.connection.execute(
            "DELETE FROM agent_profiles WHERE agent_id IN (?, ?)",
            ("agent-m170-alpha", "agent-m170-beta"),
        )
        app.state.connection.commit()

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.1",
                        "agents": ["agent-m170-alpha", "agent-m170-beta"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

        second_listing = client.get("/im/v1/agents")
        assert second_listing.status_code == 200
        assert [item["agent_id"] for item in second_listing.json()] == [
            "agent-m170-alpha",
            "agent-m170-beta",
        ]
        assert [item["display_name"] for item in second_listing.json()] == [
            "M170 Alpha",
            "M170 Beta",
        ]


def test_fresh_runtime_agents_can_back_group_creation_before_bind(
    tmp_path: Path,
) -> None:
    """A fresh gateway runtime should expose agents early enough for real group creation."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user_id = seed_user(client, "alice")

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["Alpha", "Beta"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            listed = client.get("/im/v1/agents")
            assert listed.status_code == 200
            assert [item["agent_id"] for item in listed.json()] == ["Alpha", "Beta"]

            agent_a_user_id = seed_user(client, "agent:Alpha", "Alpha")
            agent_b_user_id = seed_user(client, "agent:Beta", "Beta")

            class _Shim:
                def __init__(self, uid: str) -> None:
                    self._uid = uid

                status_code = 201

                def json(self):
                    return {"id": self._uid}

            agent_a_user = _Shim(agent_a_user_id)
            agent_b_user = _Shim(agent_b_user_id)
            assert agent_a_user.status_code == 201
            assert agent_b_user.status_code == 201

            created = client.post(
                "/im/v1/conversations",
                json={
                    "title": "Fresh Runtime Group",
                    "participant_ids": [
                        user_id,
                        agent_a_user.json()["id"],
                        agent_b_user.json()["id"],
                    ],
                },
            )
            assert created.status_code == 201
            body = created.json()
            assert body["type"] == "group"
            assert set(body["participant_ids"]) == {
                user_id,
                agent_a_user.json()["id"],
                agent_b_user.json()["id"],
            }
