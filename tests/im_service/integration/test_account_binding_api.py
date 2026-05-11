"""Integration tests for IM account and device binding APIs (post feat-340-M1 R4)."""

from pathlib import Path

from IM.infra.repositories import AgentProfileRepository, NodeRepository

from .conftest import authorize, make_app_client, register_user


def test_me_roundtrip_and_bind_flow(tmp_path: Path) -> None:
    """Read/update /me and complete the device bind flow through token-authed APIs."""
    with make_app_client(tmp_path) as client:
        owner = register_user(client, username="alice", display_name="Alice")
        authorize(client, owner)

        nodes = NodeRepository(client.app.state.connection)
        nodes.upsert_node(node_id="node-1", node_name="MacBook")
        profiles = AgentProfileRepository(client.app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-1",
            owner_id="",
            display_name="Alpha",
            description="node local",
            system_prompt="You are Alpha.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
        client.app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-1", "agent-1"),
        )
        client.app.state.connection.commit()

        me_resp = client.get("/im/v1/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["owned_node_ids"] == []
        assert me_resp.json()["default_entry_node_id"] is None

        patch_resp = client.patch(
            "/im/v1/me",
            json={"display_name": "Alice Cooper", "default_entry_node_id": None},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["display_name"] == "Alice Cooper"

        start_resp = client.post("/im/v1/bind", json={"action": "start", "node_id": "node-1"})
        assert start_resp.status_code == 201
        start_body = start_resp.json()
        assert start_body["status"] == "pending"
        assert start_body["bind_url"].startswith("http://testserver/bind/confirm?token=")

        confirm_resp = client.post(
            "/im/v1/bind",
            json={
                "action": "confirm",
                "bind_token": start_body["bind_url"].split("token=", 1)[1],
            },
        )
        assert confirm_resp.status_code == 201
        assert confirm_resp.json()["status"] == "confirmed"
        assert confirm_resp.json()["user_id"] == owner.id

        me_after_resp = client.get("/im/v1/me")
        assert me_after_resp.status_code == 200
        assert me_after_resp.json()["owned_node_ids"] == ["node-1"]
        assert me_after_resp.json()["default_entry_node_id"] == "node-1"

        default_entry_resp = client.patch(
            "/im/v1/me",
            json={"display_name": "Alice Cooper", "default_entry_node_id": "node-1"},
        )
        assert default_entry_resp.status_code == 200
        assert default_entry_resp.json()["default_entry_node_id"] == "node-1"

        profile_resp = client.get("/im/v1/agents/agent-1/config")
        assert profile_resp.status_code == 200
        assert profile_resp.json()["owner_id"] == owner.owner_id


def test_bind_rejects_unknown_references(tmp_path: Path) -> None:
    """Return stable errors for missing bind graph references."""
    with make_app_client(tmp_path) as client:
        user = register_user(client, username="alice")
        authorize(client, user)
        start_resp = client.post("/im/v1/bind", json={"action": "start", "node_id": "missing-node"})
        assert start_resp.status_code == 404
        assert start_resp.json()["detail"] == "node_id not found"

        confirm_resp = client.post(
            "/im/v1/bind",
            json={"action": "confirm", "bind_id": "missing-bind"},
        )
        assert confirm_resp.status_code == 404
        assert confirm_resp.json()["detail"] == "bind_id not found"
