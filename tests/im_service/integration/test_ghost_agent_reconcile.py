"""Integration tests for ghost-agent reconcile on Gateway register (bugfix-362-M1).

Verifies:
- _handle_register marks old agents stale when new advertise omits them
- GET /im/v1/agents excludes stale agents
- GET /im/v1/conversations/{id} includes is_stale=True for stale participants
- Re-registering with old agent revives it (is_stale becomes False)
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app

from .conftest import authorize, register_user, seed_user_under_owner


def _register_node(ws, *, node_id: str, agents: list[str]) -> dict:
    ws.send_json(
        {
            "type": "node.register",
            "payload": {
                "node_id": node_id,
                "node_name": node_id,
                "version": "1.0.0",
                "agents": agents,
                "capabilities": {"relay": True},
            },
        }
    )
    return ws.receive_json()


def test_gateway_registration_hides_removed_agent_and_revives_it(
    tmp_path: Path,
) -> None:
    """Reflect an agent disappearing and returning across Gateway registrations."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user = register_user(client, username="alice", display_name="Alice")
        authorize(client, user)

        with client.websocket_connect("/im/ws/gateway") as ws:
            # First register: A + X
            ack = _register_node(ws, node_id="node-1", agents=["agent-a", "agent-x"])
            assert ack["payload"]["message_type"] == "node.register"

            # Verify both are visible
            agents_resp = client.get("/im/v1/agents").json()
            agent_ids = {a["agent_id"] for a in agents_resp}
            assert "agent-a" in agent_ids
            assert "agent-x" in agent_ids

            # Re-register without X
            ack2 = _register_node(ws, node_id="node-1", agents=["agent-a"])
            assert ack2["payload"]["message_type"] == "node.register"

        # After reconnect, X must be gone from the list
        agents_resp2 = client.get("/im/v1/agents").json()
        agent_ids2 = {a["agent_id"] for a in agents_resp2}
        assert "agent-a" in agent_ids2
        assert "agent-x" not in agent_ids2

        with client.websocket_connect("/im/ws/gateway") as ws:
            _register_node(ws, node_id="node-1", agents=["agent-a", "agent-x"])

        revived_agents = client.get("/im/v1/agents").json()
        assert "agent-x" in {agent["agent_id"] for agent in revived_agents}


def test_conversation_participant_is_stale_exposed(tmp_path: Path) -> None:
    """GET /im/v1/conversations/{id} must expose is_stale=True for stale agent participants."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user = register_user(client, username="alice", display_name="Alice")
        authorize(client, user)

        with client.websocket_connect("/im/ws/gateway") as ws:
            _register_node(ws, node_id="node-1", agents=["agent-a", "agent-x"])

        # Seed the agent user rows so conversation participants can resolve them.
        # ws register writes agent_profiles but not users; we seed users manually.
        agent_x_user_id = seed_user_under_owner(
            client,
            username="agent:agent-x",
            display_name="Agent X",
            owner_id=user.owner_id,
        )

        # Create a group conversation with X as participant (using user_id reference)
        conv_resp = client.post(
            "/im/v1/conversations",
            json={
                "title": "group",
                "participant_ids": [agent_x_user_id],
            },
        )
        assert conv_resp.status_code == 201
        conv_id = conv_resp.json()["id"]

        # Mark agent-x stale via re-register without X
        with client.websocket_connect("/im/ws/gateway") as ws:
            _register_node(ws, node_id="node-1", agents=["agent-a"])

        # Fetch conversation – agent-x participant should have is_stale=True
        detail = client.get(f"/im/v1/conversations/{conv_id}").json()
        participants = detail["participants"]
        stale_flags = {
            p["id"]: p.get("is_stale") for p in participants if p["type"] == "agent"
        }
        assert stale_flags.get("agent-x") is True
