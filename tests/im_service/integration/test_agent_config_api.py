"""Integration tests for IM agent configuration APIs."""

from pathlib import Path
import threading

import pytest
from fastapi.testclient import TestClient

from IM.api.routes import agents as agent_routes
from IM.app import create_app
from IM.repositories import AgentProfileRepository, NodeRepository, UserRepository

_WORKSPACE_PATH_SETTING = "/Users/czj/nano-assistant/workspace/fuck"


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
                "node_id": "node-1",
                "display_name": "Alpha",
                "description": "initial",
                "profile_version": 1,
                "default_model": "gpt-4.1",
                "workspace_root": list_resp.json()[0]["workspace_root"],
                "workspace_is_default": True,
                "updated_at": list_resp.json()[0]["updated_at"],
            }
        ]
        assert list_resp.json()[0]["workspace_root"].endswith("/nano-assistant/workspace/agent-1")

        get_resp = client.get(f"/im/v1/agents/{seeded.agent_id}/config?source=mirror")
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
                "workspace_root": _WORKSPACE_PATH_SETTING,
            },
        )
        assert patch_resp.status_code == 200
        body = patch_resp.json()
        assert body["display_name"] == "Alpha v2"
        assert body["profile_version"] == 2
        assert body["group_reply_policy"] == "auto"
        assert body["workspace_root"].endswith("/nano-assistant/workspace/agent-1")
        assert body["workspace_is_default"] is True

        reset_resp = client.patch(
            f"/im/v1/agents/{seeded.agent_id}/config",
            json={
                "profile_version": 2,
                "display_name": "Alpha default",
                "description": "default workspace",
                "system_prompt": "You are Alpha default.",
                "skills": ["plan"],
                "tool_allowlist": ["read"],
                "group_reply_policy": "manual",
                "default_model": None,
                "workspace_root": None,
            },
        )
        assert reset_resp.status_code == 200
        reset_body = reset_resp.json()
        assert reset_body["profile_version"] == 3
        assert reset_body["workspace_is_default"] is True
        assert reset_body["workspace_root"].endswith("/nano-assistant/workspace/agent-1")
        stored_row = app.state.connection.execute(
            "SELECT workspace_root FROM agent_profiles WHERE agent_id = ?",
            (seeded.agent_id,),
        ).fetchone()
        assert stored_row is not None
        assert stored_row["workspace_root"].endswith("/nano-assistant/workspace/agent-1")

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


def test_get_agent_config_prefers_live_gateway_snapshot(tmp_path: Path) -> None:
    """Read agent config through the connected gateway so IM cache becomes a mirror, not the runtime source."""
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
        profiles.upsert_profile(
            agent_id="agent-1",
            owner_id=owner.owner_id,
            display_name="Cached Alpha",
            description="cached",
            system_prompt="cached prompt",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
        app.state.connection.execute("UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?", ("node-1", "agent-1"))
        app.state.connection.commit()

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-1"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            result: dict[str, object] = {}

            def _fetch() -> None:
                result["response"] = client.get("/im/v1/agents/agent-1/config")

            worker = threading.Thread(target=_fetch)
            worker.start()
            request_frame = websocket.receive_json()
            assert request_frame["type"] == "agent.config.get"
            request_id = request_frame["payload"]["request_id"]
            assert request_frame["payload"]["agent_id"] == "agent-1"
            websocket.send_json(
                {
                    "type": "agent.config",
                    "payload": {
                        "request_id": request_id,
                        "agent_id": "agent-1",
                        "agent": {
                            "display_name": "Live Alpha",
                            "system_prompt": "live prompt",
                            "skills": ["plan"],
                            "tool_allowlist": ["read"],
                            "group_reply_policy": "auto",
                            "default_model": "claude-sonnet-4",
                            "workspace_root": _WORKSPACE_PATH_SETTING,
                        },
                    },
                }
            )
            assert websocket.receive_json() == {
                "type": "ack",
                "payload": {
                    "message_type": "agent.config",
                    "request_id": request_id,
                    "agent_id": "agent-1",
                },
            }
            worker.join(timeout=5)

        response = result["response"]
        assert response.status_code == 200
        assert response.json()["display_name"] == "Live Alpha"

        mirror_response = client.get("/im/v1/agents/agent-1/config?source=mirror")
        assert mirror_response.status_code == 200
        assert mirror_response.json()["display_name"] == "Cached Alpha"
        assert response.json()["system_prompt"] == "live prompt"
        assert response.json()["skills"] == ["plan"]
        assert response.json()["tool_allowlist"] == ["read"]
        assert response.json()["group_reply_policy"] == "auto"
        assert response.json()["default_model"] == "claude-sonnet-4"
        assert response.json()["workspace_root"] == _WORKSPACE_PATH_SETTING
        assert response.json()["owner_id"] == owner.owner_id
        assert response.json()["profile_version"] == 1


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
        assert response.json()[0]["node_id"] == "node-1"



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
                "node_id": "node-fresh",
                "display_name": "Fresh Agent",
                "description": "advertised by an unbound runtime",
                "profile_version": 1,
                "default_model": None,
                "workspace_root": response.json()[0]["workspace_root"],
                "workspace_is_default": True,
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


def test_bound_agent_survives_fresh_reregistration_and_remains_updatable(tmp_path: Path) -> None:
    """Fresh runtime re-registration must not clear ownership from a previously bound agent profile."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="owner", display_name="Owner")
        nodes = NodeRepository(app.state.connection)
        profiles = AgentProfileRepository(app.state.connection)

        nodes.upsert_node(node_id="node-fresh", node_name="Fresh Runtime", status="online", version="1.0.0")
        profiles.upsert_profile(
            agent_id="agent-m170-alpha",
            owner_id="",
            display_name="Alpha",
            description="fresh runtime agent",
            system_prompt="You are Alpha.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-fresh", "agent-m170-alpha"),
        )
        app.state.connection.commit()

        start_resp = client.post("/im/v1/bind", json={"action": "start", "node_id": "node-fresh"})
        assert start_resp.status_code == 201
        confirm_resp = client.post(
            "/im/v1/bind",
            json={
                "action": "confirm",
                "bind_token": start_resp.json()["bind_url"].split("token=", 1)[1],
                "user_id": owner.id,
            },
        )
        assert confirm_resp.status_code == 201

        bound_profile = client.get("/im/v1/agents/agent-m170-alpha/config")
        assert bound_profile.status_code == 200
        assert bound_profile.json()["owner_id"] == owner.owner_id
        assert bound_profile.json()["profile_version"] == 1

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-fresh",
                        "node_name": "Fresh Runtime",
                        "version": "1.0.1",
                        "agents": ["agent-m170-alpha"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            ack = websocket.receive_json()
            assert ack["type"] == "ack"

        after_reregister = client.get("/im/v1/agents/agent-m170-alpha/config")
        assert after_reregister.status_code == 200
        assert after_reregister.json()["owner_id"] == owner.owner_id

        patch_resp = client.patch(
            "/im/v1/agents/agent-m170-alpha/config",
            json={
                "profile_version": after_reregister.json()["profile_version"],
                "display_name": "Alpha NO_REPLY",
                "description": "updated after fresh re-registration",
                "system_prompt": "Return NO_REPLY.",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "manual",
                "default_model": None,
                "workspace_root": None,
            },
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["owner_id"] == owner.owner_id
        assert patch_resp.json()["display_name"] == "Alpha NO_REPLY"


def test_node_capabilities_return_current_selectable_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Expose current gateway-resolved skill/tool/model items for the settings UI."""

    async def _fake_node_capabilities(self, *, target_node_id: str, timeout_seconds: float = 15.0):  # noqa: ARG002
        return {
            "skills": ["plan", "playwright"],
            "tools": ["read", "bash"],
            "models": ["moonshotAnthropic:kimi-k2.5", "codex_oauth:gpt-5.4"],
        }

    from IM.ws.gateway_handler import GatewayHandler

    monkeypatch.setattr(GatewayHandler, "request_node_capabilities", _fake_node_capabilities)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(node_id="node-1", node_name="MacBook", status="online", version="1.0.0")
        response = client.get("/im/v1/nodes/node-1/capabilities")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["skills"]] == ["plan", "playwright"]
    assert [item["name"] for item in response.json()["tools"]] == ["read", "bash"]
    assert response.json()["models"] == ["moonshotAnthropic:kimi-k2.5", "codex_oauth:gpt-5.4"]
