"""Recovery contracts for durable IM-originated Gateway create operations."""

from pathlib import Path
import threading

from fastapi.testclient import TestClient

from IM.app import create_app
from tests.im_service._auth_helpers import authorize, register_user


def _bind_gateway(client: TestClient, *, node_id: str) -> object:
    websocket = client.websocket_connect("/im/ws/gateway")
    websocket.__enter__()
    websocket.send_json(
        {
            "type": "node.register",
            "payload": {"node_id": node_id, "node_name": "Gateway", "version": "1", "agents": []},
        }
    )
    assert websocket.receive_json()["type"] == "ack"
    bind_start = client.post("/im/v1/bind", json={"action": "start", "node_id": node_id})
    assert bind_start.status_code == 201
    assert client.post(
        "/im/v1/bind", json={"action": "confirm", "bind_id": bind_start.json()["bind_id"]}
    ).status_code == 201
    return websocket


def _payload(agent_id: str = "recovered-agent") -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "owner_id": "",
        "display_name": "Recovered Agent",
        "description": "Recovered after a lost response.",
        "skills": [],
        "tool_allowlist": [],
        "group_reply_policy": "MENTION",
        "workspace_root": "/gateway/staging/../recovered-agent",
    }


def _register_created_agent(
    websocket: object, *, agent_id: str, operation_id: str, root: str = "/gateway/recovered-agent", is_default: bool = False
) -> None:
    websocket.send_json(
        {
            "type": "node.register",
            "payload": {
                "node_id": "node-bound-seed",
                "node_name": "Gateway",
                "version": "1.1",
                "agents": [agent_id],
                "agent_workspaces": {agent_id: root},
                "agent_workspace_is_default": {agent_id: is_default},
                "agent_create_operations": {agent_id: operation_id},
            },
        }
    )
    assert websocket.receive_json()["type"] == "ack"


def _pending_rows(app: object, *, agent_id: str) -> dict[str, list[dict[str, object]]]:
    """Capture every durable row that a rejected recovery retry must preserve."""
    connection = app.state.connection
    return {
        "agent_profiles": [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM agent_profiles WHERE agent_id = ?", (agent_id,)
            ).fetchall()
        ],
        "agent_create_operations": [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM agent_create_operations WHERE agent_id = ?", (agent_id,)
            ).fetchall()
        ],
    }


def test_ordinary_first_seen_registration_is_never_claimable(tmp_path: Path) -> None:
    """A pre-hosted first registration has no create-operation authority."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="bound-owner")
        authorize(client, owner)
        websocket = _bind_gateway(client, node_id="node-bound-seed")
        try:
            _register_created_agent(
                websocket,
                agent_id="prehosted-agent",
                operation_id="not-a-reservation",
            )
            # A Gateway may advertise an arbitrary local id, but IM did not reserve
            # this operation; it must remain a normal existing profile.
            response = client.post(
                "/im/v1/nodes/node-bound-seed/agents", json=_payload("prehosted-agent")
            )
            stored = dict(
                app.state.connection.execute(
                    "SELECT registration_seed, pending_create_operation_id FROM agent_profiles WHERE agent_id = ?",
                    ("prehosted-agent",),
                ).fetchone()
            )
        finally:
            websocket.__exit__(None, None, None)

    assert response.status_code == 409
    assert stored == {"registration_seed": 0, "pending_create_operation_id": None}


def test_lost_create_response_recovers_only_matching_durable_operation(tmp_path: Path) -> None:
    """A retry recovers the exact operation after Gateway re-registers its result."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="bound-owner")
        authorize(client, owner)
        websocket = _bind_gateway(client, node_id="node-bound-seed")
        payload = _payload()
        try:
            async def lost_response(**_kwargs):
                return None

            app.state.gateway_control.request_agent_create = lost_response
            initial = client.post("/im/v1/nodes/node-bound-seed/agents", json=payload)
            operation = app.state.connection.execute(
                "SELECT operation_id FROM agent_create_operations WHERE agent_id = ?",
                ("recovered-agent",),
            ).fetchone()["operation_id"]
            _register_created_agent(
                websocket, agent_id="recovered-agent", operation_id=operation
            )
            pending_state = _pending_rows(app, agent_id="recovered-agent")
            dispatches: list[dict[str, object]] = []

            async def unexpected_dispatch(**kwargs):
                dispatches.append(kwargs)
                raise AssertionError("a divergent retry must not reach Gateway")

            app.state.gateway_control.request_agent_create = unexpected_dispatch
            different_request = client.post(
                "/im/v1/nodes/node-bound-seed/agents",
                json={**payload, "display_name": "Different request"},
            )
            state_after_different_request = _pending_rows(
                app, agent_id="recovered-agent"
            )

            async def wrong_operation(**kwargs):
                return {
                    "agent_id": "recovered-agent",
                    "display_name": "Recovered Agent",
                    "description": "Recovered after a lost response.",
                    "workspace_root": "/gateway/recovered-agent",
                    "workspace_is_default": False,
                    "create_operation_id": "wrong-operation-id",
                }

            app.state.gateway_control.request_agent_create = wrong_operation
            wrong_operation_rejected = client.post(
                "/im/v1/nodes/node-bound-seed/agents", json=payload
            )
            state_after_wrong_operation = _pending_rows(app, agent_id="recovered-agent")

            async def wrong_root(**kwargs):
                return {
                    "agent_id": "recovered-agent",
                    "display_name": "Recovered Agent",
                    "description": "Recovered after a lost response.",
                    "workspace_root": "/gateway/other",
                    "workspace_is_default": False,
                    "create_operation_id": kwargs["payload"]["create_operation_id"],
                }

            async def wrong_provenance(**kwargs):
                return {
                    "agent_id": "recovered-agent",
                    "display_name": "Recovered Agent",
                    "description": "Recovered after a lost response.",
                    "workspace_root": "/gateway/recovered-agent",
                    "workspace_is_default": True,
                    "create_operation_id": kwargs["payload"]["create_operation_id"],
                }

            async def wrong_display(**kwargs):
                return {
                    "agent_id": "recovered-agent",
                    "display_name": "Different Agent",
                    "description": "Recovered after a lost response.",
                    "workspace_root": "/gateway/recovered-agent",
                    "workspace_is_default": False,
                    "create_operation_id": kwargs["payload"]["create_operation_id"],
                }

            app.state.gateway_control.request_agent_create = wrong_root
            root_rejected = client.post("/im/v1/nodes/node-bound-seed/agents", json=payload)
            app.state.gateway_control.request_agent_create = wrong_provenance
            provenance_rejected = client.post(
                "/im/v1/nodes/node-bound-seed/agents", json=payload
            )
            app.state.gateway_control.request_agent_create = wrong_display
            display_rejected = client.post(
                "/im/v1/nodes/node-bound-seed/agents", json=payload
            )
            app.state.connection.execute(
                "UPDATE agent_create_operations SET owner_id = ? WHERE operation_id = ?",
                ("other-owner", operation),
            )
            app.state.connection.commit()
            wrong_owner_rejected = client.post(
                "/im/v1/nodes/node-bound-seed/agents", json=payload
            )
            app.state.connection.execute(
                "UPDATE agent_create_operations SET owner_id = ? WHERE operation_id = ?",
                (owner.owner_id, operation),
            )
            app.state.connection.commit()
            pending_before_claim = dict(
                app.state.connection.execute(
                    "SELECT display_name, workspace_root, workspace_is_default, pending_create_operation_id "
                    "FROM agent_profiles WHERE agent_id = ?",
                    ("recovered-agent",),
                ).fetchone()
            )

            async def recovered(**kwargs):
                return {
                    "agent_id": "recovered-agent",
                    "display_name": "Recovered Agent",
                    "description": "Recovered after a lost response.",
                    "workspace_root": "/gateway/recovered-agent",
                    "workspace_is_default": False,
                    "create_operation_id": kwargs["payload"]["create_operation_id"],
                }

            app.state.gateway_control.request_agent_create = recovered
            recovered_response = client.post(
                "/im/v1/nodes/node-bound-seed/agents", json=payload
            )
            repeated = client.post("/im/v1/nodes/node-bound-seed/agents", json=payload)
            stored = dict(
                app.state.connection.execute(
                    "SELECT owner_id, display_name, workspace_root, workspace_is_default, registration_seed, pending_create_operation_id "
                    "FROM agent_profiles WHERE agent_id = ?",
                    ("recovered-agent",),
                ).fetchone()
            )
            operation_retired = (
                app.state.connection.execute(
                    "SELECT 1 FROM agent_create_operations WHERE agent_id = ?", ("recovered-agent",)
                ).fetchone()
                is None
            )
        finally:
            websocket.__exit__(None, None, None)

    assert initial.status_code == 503
    assert different_request.status_code == 409
    assert dispatches == []
    assert state_after_different_request == pending_state
    assert wrong_operation_rejected.status_code == 409
    assert state_after_wrong_operation == pending_state
    assert [
        root_rejected.status_code,
        provenance_rejected.status_code,
        display_rejected.status_code,
        wrong_owner_rejected.status_code,
    ] == [409, 409, 409, 409]
    assert pending_before_claim == {
        "display_name": "recovered-agent",
        "workspace_root": "/gateway/recovered-agent",
        "workspace_is_default": 0,
        "pending_create_operation_id": operation,
    }
    assert recovered_response.status_code == 201, recovered_response.text
    assert repeated.status_code == 409
    assert stored == {
        "owner_id": owner.owner_id,
        "display_name": "Recovered Agent",
        "workspace_root": "/gateway/recovered-agent",
        "workspace_is_default": 0,
        "registration_seed": 0,
        "pending_create_operation_id": None,
    }
    assert operation_retired


def test_gateway_lost_response_then_reconnect_recovers_the_original_operation(
    tmp_path: Path,
) -> None:
    """The HTTP retry and a reconnected Gateway use the same durable operation id."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="reconnect-owner")
        authorize(client, owner)
        payload = _payload("reconnect-agent")
        socket = _bind_gateway(client, node_id="node-bound-seed")
        original_request = app.state.gateway_control.request_agent_create
        first_result: dict[str, object] = {}

        async def short_request(**kwargs):
            return await original_request(**kwargs, timeout_seconds=0.05)

        app.state.gateway_control.request_agent_create = short_request
        try:
            first_worker = threading.Thread(
                target=lambda: first_result.setdefault(
                    "response",
                    client.post("/im/v1/nodes/node-bound-seed/agents", json=payload),
                )
            )
            first_worker.start()
            first_frame = socket.receive_json()
            assert first_frame["type"] == "agent.create"
            operation_id = first_frame["payload"]["agent"]["create_operation_id"]
            first_worker.join(timeout=1)
            assert not first_worker.is_alive()
        finally:
            socket.__exit__(None, None, None)

        app.state.gateway_control.request_agent_create = original_request
        with client.websocket_connect("/im/ws/gateway") as reconnect:
            _register_created_agent(
                reconnect,
                agent_id="reconnect-agent",
                operation_id=operation_id,
            )
            retry_result: dict[str, object] = {}
            retry_worker = threading.Thread(
                target=lambda: retry_result.setdefault(
                    "response",
                    client.post("/im/v1/nodes/node-bound-seed/agents", json=payload),
                )
            )
            retry_worker.start()
            retry_frame = reconnect.receive_json()
            assert retry_frame["type"] == "agent.create"
            assert retry_frame["payload"]["agent"]["create_operation_id"] == operation_id
            reconnect.send_json(
                {
                    "type": "agent.created",
                    "payload": {
                        "request_id": retry_frame["payload"]["request_id"],
                        "node_id": "node-bound-seed",
                        "agent": {
                            "agent_id": "reconnect-agent",
                            "display_name": "Recovered Agent",
                            "description": "Recovered after a lost response.",
                            "workspace_root": "/gateway/recovered-agent",
                            "workspace_is_default": False,
                            "create_operation_id": operation_id,
                        },
                    },
                }
            )
            assert reconnect.receive_json()["type"] == "ack"
            assert reconnect.receive_json()["type"] == "config.sync"
            retry_worker.join(timeout=1)

    assert first_result["response"].status_code == 503
    assert not retry_worker.is_alive()
    assert retry_result["response"].status_code == 201
