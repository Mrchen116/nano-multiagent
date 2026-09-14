"""Members discover chat commands without receiving Agent management data."""

import json

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.nodes import NodeRepository
from .conftest import authorize, register_user, seed_user_under_owner


def _room(client):
    owner = register_user(client, username="owner")
    member = register_user(client, username="member")
    outsider = register_user(client, username="outsider")
    db = client.app.state.connection
    for node in ("first-node", "second-node"):
        NodeRepository(db).upsert_node(
            node_id=node, node_name=node, owner_id=owner.owner_id
        )
    profiles = AgentProfileRepository(db)
    ids = []
    for agent, node in (
        ("a", "first-node"),
        ("b", "first-node"),
        ("c", "second-node"),
        ("empty", "second-node"),
        ("offline", "second-node"),
    ):
        profiles.create_profile(
            agent_id=agent,
            owner_id=owner.owner_id,
            node_id=node,
            display_name=agent.upper(),
            description="private config description",
            skills=["stale"],
            tool_allowlist=[],
            group_reply_policy="ALWAYS",
            default_model=None,
            workspace_root=f"/private/{agent}",
        )
        ids.append(
            seed_user_under_owner(
                client, username=f"agent:{agent}", owner_id=owner.owner_id
            )
        )
    room = ConversationRepository(db).create_conversation(
        title="Shared",
        participant_ids=[member.id, *ids],
        caller_owner_id=member.owner_id,
    )
    return owner, member, outsider, room


def test_member_command_projection_preserves_enabled_sources_without_paths(
    tmp_path, monkeypatch
):
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner, member, outsider, room = _room(client)
        calls = []

        async def config(*, target_node_id, agent_id):
            calls.append((agent_id, target_node_id))
            if agent_id == "offline":
                return None
            return {
                "agent_id": agent_id,
                "skills": ["deploy"] if agent_id == "b" else [],
                "skills_selection_mode": "explicit_allowlist"
                if agent_id in {"b", "empty"}
                else "default_discovery",
                "custom_prompt": "do not expose this",
            }

        async def capabilities(*, target_node_id, agent_id, workspace_root):
            assert workspace_root == f"/private/{agent_id}"
            return {
                "skills": [
                    {
                        "name": "deploy",
                        "description": "first source",
                        "location": "/private/one/SKILL.md",
                    },
                    {
                        "name": "deploy",
                        "description": "second source",
                        "location": "/private/two/SKILL.md",
                    },
                    {"name": "notes", "description": "without a location"},
                ],
                "commands": [
                    {
                        "name": "effort",
                        "description": f"levels for {agent_id}",
                        "secret": "do not expose",
                    }
                ],
                "workspace_root": workspace_root,
                "credentials": "do not expose",
            }

        monkeypatch.setattr(app.state.gateway_control, "request_agent_config", config)
        monkeypatch.setattr(
            app.state.gateway_control, "request_agent_capabilities", capabilities
        )
        endpoint = f"/im/v1/conversations/{room.id}/commands"
        authorize(client, member)
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        items = {item["agent_id"]: item for item in response.json()["items"]}
        assert items["a"]["status"] == "available"
        assert len(items["a"]["skills"]) == 3
        assert len(items["b"]["skills"]) == 2
        assert items["empty"]["skills"] == []
        assert items["offline"] == {
            "agent_id": "offline",
            "display_name": "OFFLINE",
            "status": "unavailable",
            "skills": [],
            "commands": [],
        }
        first, second, no_location = items["a"]["skills"]
        assert first["skill_key"] != second["skill_key"]
        assert first["skill_key"] == items["b"]["skills"][0]["skill_key"]
        assert first["skill_key"] != items["c"]["skills"][0]["skill_key"]
        assert no_location["skill_key"] != items["c"]["skills"][2]["skill_key"]
        assert items["a"]["commands"] == [
            {"name": "effort", "description": "levels for a"}
        ]
        assert "/private" not in response.text
        assert "do not expose" not in response.text
        assert all(
            set(skill) == {"skill_key", "name", "description"}
            for item in items.values()
            for skill in item["skills"]
        )
        assert ("a", "first-node") in calls and ("c", "second-node") in calls
        assert client.get(endpoint).json() == response.json()
        assert client.get("/im/v1/agents/a/config").status_code == 404
        before = len(calls)
        for user in (outsider, owner):
            authorize(client, user)
            assert client.get(endpoint).status_code == 404
        assert len(calls) == before
        client.headers.pop("Authorization")
        assert client.get(endpoint).status_code == 401


def test_command_projection_rechecks_membership_after_gateway_io(tmp_path, monkeypatch):
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        _, member, _, room = _room(client)

        async def config(**kwargs):
            return {"skills": [], "skills_selection_mode": "default_discovery"}

        async def capabilities(**kwargs):
            with app.state.connection:
                app.state.connection.execute(
                    "DELETE FROM conversation_participants WHERE conversation_id=? AND user_id=?",
                    (room.id, member.id),
                )
            return {"skills": [{"name": "deploy", "location": "/private/skill"}]}

        monkeypatch.setattr(app.state.gateway_control, "request_agent_config", config)
        monkeypatch.setattr(
            app.state.gateway_control, "request_agent_capabilities", capabilities
        )
        authorize(client, member)
        response = client.get(f"/im/v1/conversations/{room.id}/commands")
        assert response.status_code == 404
        assert "deploy" not in json.dumps(response.json())
