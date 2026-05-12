"""M18 R9-1: agent registration must synchronously provision an IM user row.

Background: R9 final acceptance found that `POST /im/v1/nodes/{node_id}/agents`
creates an agent profile but **does not** create the matching IM users row.
The list endpoint then returns ``user_id: null``, making the
``POST /im/v1/conversations { participant_ids: [agent.user_id] }`` flow fail
with 400 ``participant_ids contains unknown users``. End-user cannot start a
direct chat with the freshly-created agent.

These tests pin the contract: agent creation **and** legacy reads must surface
a usable ``user_id`` for every agent.
"""

from pathlib import Path
import threading

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import NodeRepository, UserRepository

from .conftest import authorize, register_user

_WORKSPACE_SETTING = "/Users/czj/nano-assistant/workspace/m18"


def test_create_node_agent_provisions_im_user_row_atomically(tmp_path: Path) -> None:
    """POST /im/v1/nodes/{node}/agents creates `users` row username=agent:<id>."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-m18",
            node_name="MacBook",
            status="online",
            version="1.0.0",
            owner_id=owner.owner_id,
        )

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-m18",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": [],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            captured: dict[str, object] = {}

            def _post() -> None:
                captured["resp"] = client.post(
                    "/im/v1/nodes/node-m18/agents",
                    json={
                        "agent_id": "agent-m18-new",
                        "owner_id": owner.owner_id,
                        "display_name": "M18 Beta",
                        "description": "freshly minted",
                        "system_prompt": "You are M18 Beta.",
                        "skills": [],
                        "tool_allowlist": [],
                        "group_reply_policy": "MENTION",
                        "default_model": None,
                    },
                )

            worker = threading.Thread(target=_post)
            worker.start()
            create_req = websocket.receive_json()
            assert create_req["type"] == "agent.create"
            websocket.send_json(
                {
                    "type": "agent.created",
                    "payload": {
                        "request_id": create_req["payload"]["request_id"],
                        "node_id": "node-m18",
                        "agent": {
                            "agent_id": "agent-m18-new",
                            "display_name": "M18 Beta",
                            "description": "freshly minted",
                            "system_prompt": "You are M18 Beta.",
                            "skills": [],
                            "tool_allowlist": [],
                            "group_reply_policy": "MENTION",
                            "default_model": None,
                            "workspace_root": _WORKSPACE_SETTING,
                        },
                    },
                }
            )
            # absorb ack + config.sync emitted by the route
            websocket.receive_json()
            websocket.receive_json()
            worker.join(timeout=5)

        resp = captured["resp"]
        assert resp.status_code == 201

        users = UserRepository(app.state.connection)
        provisioned = users.get_user_by_username(username="agent:agent-m18-new")
        assert provisioned is not None, "agent registration must provision matching users row"
        assert provisioned.display_name == "M18 Beta"

        listed = client.get("/im/v1/agents")
        assert listed.status_code == 200
        rows = listed.json()
        assert any(row["agent_id"] == "agent-m18-new" and row["user_id"] == provisioned.id for row in rows)


def test_list_agents_lazy_provisions_user_row_for_legacy_seed(tmp_path: Path) -> None:
    """GET /im/v1/agents auto-creates a users row for agent profiles that pre-date M18."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        from IM.repositories import AgentProfileRepository

        profiles = AgentProfileRepository(app.state.connection)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-legacy",
            node_name="MacBook",
            status="online",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles.upsert_profile(
            agent_id="legacy-seed",
            owner_id=owner.owner_id,
            display_name="Legacy Seed",
            description="",
            system_prompt="…",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="MENTION",
            default_model=None,
            workspace_root=None,
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?", ("node-legacy", "legacy-seed")
        )
        app.state.connection.commit()

        users = UserRepository(app.state.connection)
        assert users.get_user_by_username(username="agent:legacy-seed") is None

        listed = client.get("/im/v1/agents")
        assert listed.status_code == 200
        row = next(item for item in listed.json() if item["agent_id"] == "legacy-seed")
        assert row["user_id"] is not None, "legacy seed agent must surface a real user_id via lazy bootstrap"

        provisioned = users.get_user_by_username(username="agent:legacy-seed")
        assert provisioned is not None
        assert row["user_id"] == provisioned.id
