"""End-to-end WS correlation for recoverable workspace creation errors."""

from pathlib import Path
import threading

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.nodes import NodeRepository
from tests.im_service._auth_helpers import authorize, register_user


def test_gateway_workspace_error_reaches_http_as_structured_conflict(
    tmp_path: Path,
) -> None:
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1", node_name="MacBook", owner_id=owner.owner_id
        )

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "agents": [],
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            result: dict[str, object] = {}

            def create_agent() -> None:
                result["response"] = client.post(
                    "/im/v1/nodes/node-1/agents",
                    json={
                        "agent_id": "agent-1",
                        "owner_id": owner.owner_id,
                        "display_name": "Alpha",
                        "skills": [],
                        "tool_allowlist": [],
                        "group_reply_policy": "MENTION",
                        "workspace_root": "/srv/existing",
                        "confirm_existing_workspace": False,
                    },
                )

            worker = threading.Thread(target=create_agent)
            worker.start()
            request = websocket.receive_json()
            assert request["type"] == "agent.create"
            assert request["payload"]["agent"]["confirm_existing_workspace"] is False
            websocket.send_json(
                {
                    "type": "agent.created",
                    "payload": {
                        "request_id": request["payload"]["request_id"],
                        "node_id": "node-1",
                        "agent": {},
                        "error": {
                            "code": "workspace_confirmation_required",
                            "detail": "Workspace target requires confirmation.",
                        },
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            worker.join(timeout=5)

        assert not worker.is_alive()
        response = result["response"]
        assert response.status_code == 409
        assert response.json() == {
            "code": "workspace_confirmation_required",
            "detail": "Workspace target requires confirmation.",
        }
