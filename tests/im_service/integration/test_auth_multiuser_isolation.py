"""R6 cross-tenant isolation e2e: each resource type returns 404 across tenants."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories import AgentProfileRepository, NodeRepository

from .conftest import authorize, register_user


def _build_two_tenants(tmp_path: Path):
    app = create_app(db_path=tmp_path / "im.db")
    alice_client = TestClient(app)
    bob_client = TestClient(app)
    alice_client.__enter__()
    bob_client.__enter__()
    alice = register_user(alice_client, username="alice")
    bob = register_user(bob_client, username="bob")
    authorize(alice_client, alice)
    authorize(bob_client, bob)
    return app, alice_client, alice, bob_client, bob


def test_conversation_404_across_tenants(tmp_path: Path) -> None:
    """Bob cannot GET/PATCH/DELETE Alice's conversation."""
    app, alice_client, alice, bob_client, bob = _build_two_tenants(tmp_path)
    try:
        del app, bob
        alice_conv = alice_client.post(
            "/im/v1/conversations",
            json={"title": "Alice's room", "participant_ids": [alice.id]},
        ).json()
        cid = alice_conv["id"]

        assert bob_client.get(f"/im/v1/conversations/{cid}").status_code == 404
        assert bob_client.patch(f"/im/v1/conversations/{cid}", json={"is_pinned": True}).status_code == 404
        assert bob_client.delete(f"/im/v1/conversations/{cid}").status_code == 404
    finally:
        alice_client.__exit__(None, None, None)
        bob_client.__exit__(None, None, None)


def test_message_404_across_tenants(tmp_path: Path) -> None:
    """Bob cannot post or list messages on Alice's conversation."""
    app, alice_client, alice, bob_client, bob = _build_two_tenants(tmp_path)
    try:
        del app
        cid = alice_client.post(
            "/im/v1/conversations",
            json={"title": "Alice's room", "participant_ids": [alice.id]},
        ).json()["id"]

        assert bob_client.get(f"/im/v1/conversations/{cid}/messages").status_code == 404
        assert bob_client.post(
            f"/im/v1/conversations/{cid}/messages",
            json={"sender_user_id": bob.id, "content": "intrude"},
        ).status_code == 404
    finally:
        alice_client.__exit__(None, None, None)
        bob_client.__exit__(None, None, None)


def test_agent_404_across_tenants(tmp_path: Path) -> None:
    """Bob cannot read/patch Alice's agent profile."""
    app, alice_client, alice, bob_client, bob = _build_two_tenants(tmp_path)
    try:
        del bob
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="alice-agent",
            owner_id=alice.owner_id,
            display_name="Alice's Agent",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root="/tmp/a",
        )
        NodeRepository(app.state.connection).upsert_node(node_id="node-alice", node_name="N", owner_id=alice.owner_id)
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?", ("node-alice", "alice-agent")
        )
        app.state.connection.commit()

        assert bob_client.get("/im/v1/agents/alice-agent/config").status_code == 404
        assert bob_client.patch(
            "/im/v1/agents/alice-agent/config",
            json={
                "profile_version": 1,
                "display_name": "x",
                "description": "",
                "system_prompt": "",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "manual",
                "default_model": None,
            },
        ).status_code == 404

        bob_list = bob_client.get("/im/v1/agents")
        assert bob_list.status_code == 200
        assert "alice-agent" not in [item["agent_id"] for item in bob_list.json()]
    finally:
        alice_client.__exit__(None, None, None)
        bob_client.__exit__(None, None, None)


def test_node_404_across_tenants(tmp_path: Path) -> None:
    """Bob cannot read/update Alice's node config."""
    app, alice_client, alice, bob_client, bob = _build_two_tenants(tmp_path)
    try:
        del bob
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-alice", node_name="Alice Node", owner_id=alice.owner_id
        )

        assert bob_client.get("/im/v1/nodes/node-alice/capabilities").status_code == 404
        assert bob_client.patch("/im/v1/nodes/node-alice/config", json={"alias": "x"}).status_code == 404
        bob_list = bob_client.get("/im/v1/nodes")
        assert bob_list.status_code == 200
        assert "node-alice" not in [item["node_id"] for item in bob_list.json()]
    finally:
        alice_client.__exit__(None, None, None)
        bob_client.__exit__(None, None, None)


def test_me_returns_each_users_own_record(tmp_path: Path) -> None:
    """/me returns the bearer-token subject; bob sees bob, alice sees alice."""
    _, alice_client, alice, bob_client, bob = _build_two_tenants(tmp_path)
    try:
        alice_me = alice_client.get("/im/v1/me").json()
        bob_me = bob_client.get("/im/v1/me").json()
        assert alice_me["id"] == alice.id
        assert bob_me["id"] == bob.id
        assert alice_me["owner_id"] != bob_me["owner_id"]
    finally:
        alice_client.__exit__(None, None, None)
        bob_client.__exit__(None, None, None)
