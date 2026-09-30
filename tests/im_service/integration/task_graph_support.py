"""Shared real HTTP/WebSocket fixture for task graph integration journeys."""

import hashlib

import pytest
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.application.config_service import ConfigService
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.nodes import NodeRepository
from IM.infra.repositories.users import UserRepository
from .conftest import authorize, register_user


@pytest.fixture(params=["global", "single_thread"])
def task_stack(tmp_path, request):
    app = create_app(db_path=tmp_path / "tasks.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        stranger = register_user(client, username="stranger")
        authorize(client, owner)
        db = app.state.connection
        db.execute("UPDATE users SET membership_status='active'")
        db.commit()
        NodeRepository(db).upsert_node(
            node_id="node", node_name="Node", owner_id=owner.owner_id
        )
        config = ConfigService(
            profiles=AgentProfileRepository(db),
            nodes=NodeRepository(db),
            users=UserRepository(db),
        )
        for agent_id in ("nano", "peer"):
            config.create_profile(
                agent_id=agent_id,
                owner_id=owner.owner_id,
                node_id="node",
                display_name="Nano",
                description="",
                skills=[],
                tool_allowlist=["task_graph"],
                group_reply_policy="ALWAYS",
                default_model=None,
                workspace_root=None,
                work_mode=request.param,
            )
        agent_user = UserRepository(db).get_user_by_username(username="agent:nano").id
        chat = ConversationRepository(db).create_conversation(
            title="Project chat",
            participant_ids=[owner.id, agent_user],
            caller_owner_id=owner.owner_id,
        )
        # The task suite starts after device enrollment; exercise the real runtime
        # authentication with a persisted node credential, not browser credentials.
        runtime_token = "task-fixture-runtime"
        db.execute(
            "INSERT INTO node_binding_state(node_id,node_epoch,runtime_token_hash,owner_id) VALUES (?,?,?,?)",
            (
                "node",
                1,
                hashlib.sha256(runtime_token.encode()).hexdigest(),
                owner.owner_id,
            ),
        )
        db.commit()
        with client.websocket_connect(
            "/im/ws/gateway", headers={"Authorization": f"Bearer {runtime_token}"}
        ) as ws:
            ws.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node",
                        "agents": ["nano", "peer"],
                        "agent_work_modes": {"nano": request.param},
                        "capabilities": {},
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "ack", response
            yield client, ws, owner, stranger, chat, agent_user


def command(ws, action, *, agent_id="nano", **args):
    ws.send_json(
        {
            "type": "task_graph.command",
            "payload": {
                "node_id": "node",
                "agent_id": agent_id,
                "request_id": "rpc",
                "action": action,
                "args": args,
            },
        }
    )
    response = ws.receive_json()
    assert response["type"] == "task_graph.result", response
    assert response["payload"]["request_id"] == "rpc"
    return response["payload"]
