"""Integration tests for IM agent configuration APIs."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.api.routes import agents as agent_routes
from IM.app import create_app
from IM.repositories import AgentProfileRepository, NodeRepository, UserRepository


def test_agents_list_get_patch_and_conflict(tmp_path: Path) -> None:
    """List runtime-selectable agents, then read and optimistically update one config."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="owner", display_name="Owner")
        profiles = AgentProfileRepository(app.state.connection)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1",
            node_name="MacBook",
            status="online",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        seeded = profiles.upsert_profile(
            agent_id="agent-1",
            owner_id=owner.owner_id,
            display_name="Alpha",
            description="initial",
            system_prompt="You are Alpha.",
            skills=["plan"],
            tool_allowlist=["read"],
            group_reply_policy="manual",
            default_model="gpt-4.1",
            workspace_root=None,
        )
        app.state.connection.execute("UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?", ("node-1", "agent-1"))
        app.state.connection.commit()

        list_resp = client.get("/im/v1/agents")
        assert list_resp.status_code == 200
        assert list_resp.json() == [
            {
                "agent_id": "agent-1",
                "owner_id": owner.owner_id,
                "display_name": "Alpha",
                "description": "initial",
                "profile_version": 1,
                "default_model": "gpt-4.1",
                "workspace_root": list_resp.json()[0]["workspace_root"],
                "workspace_is_default": True,
                "bound_nodes": ["node-1"],
                "updated_at": list_resp.json()[0]["updated_at"],
            }
        ]
        assert list_resp.json()[0]["workspace_root"].endswith("/nano-assistant/workspace/agent-1")

        get_resp = client.get(f"/im/v1/agents/{seeded.agent_id}/config")
        assert get_resp.status_code == 200
        assert get_resp.json()["profile_version"] == 1
        assert get_resp.json()["skills"] == ["plan"]
        assert get_resp.json()["workspace_is_default"] is True

        patch_resp = client.patch(
            f"/im/v1/agents/{seeded.agent_id}/config",
            json={
                "profile_version": 1,
                "display_name": "Alpha v2",
                "description": "updated",
                "system_prompt": "You are Alpha v2.",
                "skills": ["plan", "review"],
                "tool_allowlist": ["read", "edit"],
                "group_reply_policy": "auto",
                "default_model": "claude-sonnet-4",
                "workspace_root": "/srv/agents/alpha",
            },
        )
        assert patch_resp.status_code == 200
        body = patch_resp.json()
        assert body["display_name"] == "Alpha v2"
        assert body["profile_version"] == 2
        assert body["group_reply_policy"] == "auto"
        assert body["workspace_root"] == "/srv/agents/alpha"
        assert body["workspace_is_default"] is False

        conflict_resp = client.patch(
            f"/im/v1/agents/{seeded.agent_id}/config",
            json={
                "profile_version": 1,
                "display_name": "stale",
                "description": "stale",
                "system_prompt": "stale",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "manual",
                "default_model": None,
                "workspace_root": None,
            },
        )
        assert conflict_resp.status_code == 409
        assert conflict_resp.json()["detail"] == "profile_version conflict"


def test_agents_list_hides_unbound_and_cross_owner_profiles(tmp_path: Path) -> None:
    """Only bound profiles in the current runtime ownership scope should be selectable."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="owner", display_name="Owner")
        other_owner = users.create_user(username="other", display_name="Other")
        profiles = AgentProfileRepository(app.state.connection)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1",
            node_name="MacBook",
            status="online",
            version="1.0.0",
            owner_id=owner.owner_id,
        )

        profiles.upsert_profile(
            agent_id="agent-selectable",
            owner_id=owner.owner_id,
            display_name="Selectable",
            description="bound to runtime owner",
            system_prompt="You are Selectable.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
        profiles.upsert_profile(
            agent_id="agent-unbound",
            owner_id=owner.owner_id,
            display_name="Unbound",
            description="not bound to any node",
            system_prompt="You are Unbound.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
        profiles.upsert_profile(
            agent_id="agent-cross-owner",
            owner_id=other_owner.owner_id,
            display_name="Cross Owner",
            description="bound to someone else",
            system_prompt="You are Cross Owner.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id IN (?, ?)",
            ("node-1", "agent-selectable", "agent-cross-owner"),
        )
        app.state.connection.commit()

        response = client.get("/im/v1/agents")
        assert response.status_code == 200
        assert [item["agent_id"] for item in response.json()] == ["agent-selectable"]
        assert response.json()[0]["bound_nodes"] == ["node-1"]



def test_agents_list_includes_fresh_runtime_profiles_before_bind(tmp_path: Path) -> None:
    """Fresh gateway runtimes should expose ownerless bound agents before bind confirmation."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        other_owner = users.create_user(username="other", display_name="Other")
        profiles = AgentProfileRepository(app.state.connection)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-fresh",
            node_name="Fresh Runtime",
            status="online",
            version="1.0.0",
        )

        profiles.upsert_profile(
            agent_id="agent-fresh",
            owner_id="",
            display_name="Fresh Agent",
            description="advertised by an unbound runtime",
            system_prompt="You are Fresh Agent.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
        profiles.upsert_profile(
            agent_id="agent-stale-cross-owner",
            owner_id=other_owner.owner_id,
            display_name="Stale Cross Owner",
            description="stale profile attached to an unbound node",
            system_prompt="You are Stale Cross Owner.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id IN (?, ?)",
            ("node-fresh", "agent-fresh", "agent-stale-cross-owner"),
        )
        app.state.connection.commit()

        response = client.get("/im/v1/agents")
        assert response.status_code == 200
        assert response.json() == [
            {
                "agent_id": "agent-fresh",
                "owner_id": "",
                "display_name": "Fresh Agent",
                "description": "advertised by an unbound runtime",
                "profile_version": 1,
                "default_model": None,
                "workspace_root": response.json()[0]["workspace_root"],
                "workspace_is_default": True,
                "bound_nodes": ["node-fresh"],
                "updated_at": response.json()[0]["updated_at"],
            }
        ]
        assert response.json()[0]["workspace_root"].endswith("/nano-assistant/workspace/agent-fresh")



def test_profile_updates_only_affect_new_conversations(tmp_path: Path) -> None:
    """Snapshot alias-backed direct conversations so old threads stay old and new threads pick up updates."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="owner", display_name="Owner")
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-1",
            owner_id=owner.owner_id,
            display_name="Alpha",
            description="initial",
            system_prompt="You are Alpha.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )

        agent_participant = users.create_user(username="agent:agent-1", display_name="Alpha Alias")

        first_conv = client.post(
            "/im/v1/conversations",
            json={"title": "first", "participant_ids": [owner.id, agent_participant.id]},
        )
        assert first_conv.status_code == 201
        assert first_conv.json()["config_profile_version"] == 1

        patch_resp = client.patch(
            "/im/v1/agents/agent-1/config",
            json={
                "profile_version": 1,
                "display_name": "Alpha v2",
                "description": "updated",
                "system_prompt": "v2",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "manual",
                "default_model": None,
                "workspace_root": None,
            },
        )
        assert patch_resp.status_code == 200

        second_conv = client.post(
            "/im/v1/conversations",
            json={"title": "second", "participant_ids": [owner.id, agent_participant.id]},
        )
        assert second_conv.status_code == 201

        first_conv_after_patch = client.get(f"/im/v1/conversations/{first_conv.json()['id']}")
        second_conv_after_patch = client.get(f"/im/v1/conversations/{second_conv.json()['id']}")
        assert first_conv_after_patch.status_code == 200
        assert second_conv_after_patch.status_code == 200
        assert first_conv.json()["config_profile_version"] == 1
        assert first_conv_after_patch.json()["config_profile_version"] == 1
        assert second_conv.json()["config_profile_version"] == 2
        assert second_conv_after_patch.json()["config_profile_version"] == 2


def test_agent_allowlist_options_returns_current_selectable_items(tmp_path: Path, monkeypatch) -> None:
    """Expose current skill/tool options so the settings UI can render selectors."""
    monkeypatch.setattr(
        agent_routes,
        "_list_available_skill_options",
        lambda: [
            agent_routes.AllowlistOptionResponse(name="plan", description="Plan work"),
            agent_routes.AllowlistOptionResponse(name="playwright", description="Drive browser checks"),
        ],
    )
    monkeypatch.setattr(
        agent_routes,
        "_list_available_tool_options",
        lambda: [
            agent_routes.AllowlistOptionResponse(name="read", description="Read files"),
            agent_routes.AllowlistOptionResponse(name="bash", description="Run shell commands"),
        ],
    )

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        response = client.get("/im/v1/agents/allowlist-options")

    assert response.status_code == 200
    assert response.json()["skills"] == [
        {"name": "plan", "description": "Plan work"},
        {"name": "playwright", "description": "Drive browser checks"},
    ]
    assert response.json()["tools"] == [
        {"name": "read", "description": "Read files"},
        {"name": "bash", "description": "Run shell commands"},
    ]
