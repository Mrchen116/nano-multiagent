"""Contract tests for IM account and device binding endpoints."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import NodeRepository, UserRepository


def test_me_and_bind_contract_shapes(tmp_path: Path) -> None:
    """Expose stable account fields and bind response structure."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="alice", display_name="Alice")
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(node_id="node-1", node_name="MacBook")

        me_response = client.get(f"/im/v1/me?user_id={owner.id}")
        assert me_response.status_code == 200
        assert set(me_response.json()) == {
            "id",
            "user_id",
            "username",
            "display_name",
            "owner_id",
            "owned_node_ids",
            "default_entry_node_id",
            "created_at",
        }
        assert me_response.json()["user_id"] == owner.id
        assert me_response.json()["default_entry_node_id"] is None

        bind_response = client.post("/im/v1/bind", json={"action": "start", "node_id": "node-1"})
        assert bind_response.status_code == 201
        assert set(bind_response.json()) == {
            "bind_id",
            "node_id",
            "user_id",
            "status",
            "bind_url",
            "created_at",
            "confirmed_at",
        }


def test_bind_contract_requires_action_specific_fields(tmp_path: Path) -> None:
    """Return stable 400 semantics when bind action payload is incomplete."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        start_response = client.post("/im/v1/bind", json={"action": "start"})
        assert start_response.status_code == 400
        assert start_response.json() == {"detail": "node_id is required for start"}

        confirm_response = client.post("/im/v1/bind", json={"action": "confirm", "bind_id": "b1"})
        assert confirm_response.status_code == 400
        assert confirm_response.json() == {"detail": "bind_id or bind_token and user_id are required for confirm"}
