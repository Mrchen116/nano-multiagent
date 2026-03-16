"""Integration coverage for creating agent profiles and using them in relay flows."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import NodeRepository, UserRepository

_WORKSPACE_PATH_SETTING = "/Users/czj/nano-assistant/workspace/fuck"


def test_create_agent_lists_details_and_uses_new_node_binding_for_relay(tmp_path: Path) -> None:
    """Create an agent through HTTP, then use it in a real Web IM relay path."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="owner", display_name="Owner")
        human_user = users.create_user(username="alice", display_name="Alice")
        agent_user = users.create_user(username="agent:agent-new", display_name="Agent New")
        NodeRepository(app.state.connection).upsert_node(node_id="node-1", node_name="MacBook")

        created = client.post(
            "/im/v1/agents",
            json={
                "agent_id": agent_user.id,
                "owner_id": owner.owner_id,
                "display_name": "Agent New",
                "description": "runtime-created helper",
                "system_prompt": "You are Agent New.",
                "skills": ["plan"],
                "tool_allowlist": ["read"],
                "group_reply_policy": "MENTION",
                "default_model": "claude-sonnet-4",
                "workspace_root": _WORKSPACE_PATH_SETTING,
                "node_id": "node-1",
            },
        )
        assert created.status_code == 201
        assert created.json()["agent_id"] == agent_user.id
        assert created.json()["bound_nodes"] == ["node-1"]
        assert created.json()["workspace_root"] == _WORKSPACE_PATH_SETTING

        listed = client.get("/im/v1/agents")
        assert listed.status_code == 200
        assert listed.json() == [
            {
                "agent_id": agent_user.id,
                "owner_id": owner.owner_id,
                "display_name": "Agent New",
                "description": "runtime-created helper",
                "profile_version": 1,
                "default_model": "claude-sonnet-4",
                "workspace_root": _WORKSPACE_PATH_SETTING,
                "workspace_is_default": False,
                "bound_nodes": ["node-1"],
                "updated_at": created.json()["updated_at"],
            }
        ]

        detail = client.get(f"/im/v1/agents/{agent_user.id}/config")
        assert detail.status_code == 200
        assert detail.json()["bound_nodes"] == ["node-1"]
        assert detail.json()["group_reply_policy"] == "MENTION"
        assert detail.json()["workspace_root"] == _WORKSPACE_PATH_SETTING

        conversation = client.post(
            "/im/v1/conversations",
            json={"title": "new agent thread", "participant_ids": [human_user.id, agent_user.id]},
        )
        assert conversation.status_code == 201

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": [agent_user.id],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            created_message = client.post(
                f"/im/v1/conversations/{conversation.json()['id']}/messages",
                headers={"Idempotency-Key": "idem-agent-create"},
                json={
                    "sender_user_id": human_user.id,
                    "content": "hello new agent",
                    "target_node_id": "node-1",
                },
            )
            assert created_message.status_code == 201
            relay_frame = websocket.receive_json()

        assert relay_frame["type"] == "relay.message"
        assert relay_frame["payload"]["relay_task_id"]
        assert relay_frame["payload"]["idempotency_key"] == "idem-agent-create"
        assert relay_frame["payload"]["conversation_id"] == conversation.json()["id"]
        assert relay_frame["payload"]["agent_id"] == agent_user.id
        assert relay_frame["payload"]["message"]["id"] == created_message.json()["id"]
        assert relay_frame["payload"]["message"]["sender_user_id"] == human_user.id
        assert relay_frame["payload"]["message"]["content"] == "hello new agent"
        assert relay_frame["payload"]["message"]["attachments"] == []
        assert relay_frame["payload"]["message"]["id"] == created_message.json()["id"]
        assert relay_frame["payload"]["message"]["conversation_id"] == conversation.json()["id"]
        assert relay_frame["payload"]["message"]["sender_type"] == "user"
        assert relay_frame["payload"]["message"]["created_at"] == created_message.json()["created_at"]
        assert relay_frame["payload"]["metadata"] == {
            "conversation_type": "direct",
            "mentioned_agent_ids": [],
            "config_profile_version": 1,
            "system_prompt": "You are Agent New.",
        }
        relay_task = app.state.connection.execute(
            "SELECT target_node_id FROM relay_tasks WHERE relay_task_id = ?",
            (relay_frame["payload"]["relay_task_id"],),
        ).fetchone()
        assert relay_task is not None
        assert relay_task["target_node_id"] == "node-1"



def test_create_agent_without_workspace_persists_managed_default_workspace_root(tmp_path: Path) -> None:
    """Persist the managed default workspace so later session refreshes can trust profile rows."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="owner", display_name="Owner")
        agent_user = users.create_user(username="agent:agent-default", display_name="Agent Default")
        NodeRepository(app.state.connection).upsert_node(node_id="node-1", node_name="MacBook")

        created = client.post(
            "/im/v1/agents",
            json={
                "agent_id": agent_user.id,
                "owner_id": owner.owner_id,
                "display_name": "Agent Default",
                "description": "managed workspace",
                "system_prompt": "You are Agent Default.",
                "skills": ["plan"],
                "tool_allowlist": ["read"],
                "group_reply_policy": "MENTION",
                "default_model": "claude-sonnet-4",
                "node_id": "node-1",
            },
        )
        assert created.status_code == 201
        assert created.json()["workspace_is_default"] is True
        assert created.json()["workspace_root"].endswith(f"/nano-assistant/workspace/{agent_user.id}")

        row = app.state.connection.execute(
            "SELECT workspace_root FROM agent_profiles WHERE agent_id = ?",
            (agent_user.id,),
        ).fetchone()
        assert row is not None
        assert row["workspace_root"].endswith(f"/nano-assistant/workspace/{agent_user.id}")



def test_create_agent_pushes_config_sync_to_connected_gateway(tmp_path: Path) -> None:
    """Notify a connected bound node immediately when a new agent is created."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="owner", display_name="Owner")
        agent_user = users.create_user(username="agent:agent-live", display_name="Agent Live")
        NodeRepository(app.state.connection).upsert_node(node_id="node-1", node_name="MacBook")

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": [agent_user.id],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            created = client.post(
                "/im/v1/agents",
                json={
                    "agent_id": agent_user.id,
                    "owner_id": owner.owner_id,
                    "display_name": "Agent Live",
                    "description": "runtime-created helper",
                    "system_prompt": "You are Agent Live.",
                    "skills": ["plan"],
                    "tool_allowlist": ["read"],
                    "group_reply_policy": "MENTION",
                    "default_model": "claude-sonnet-4",
                    "workspace_root": _WORKSPACE_PATH_SETTING,
                    "node_id": "node-1",
                },
            )

            assert created.status_code == 201
            assert websocket.receive_json() == {
                "type": "config.sync",
                "payload": {"agent_id": agent_user.id, "profile_version": 1},
            }
