"""Integration coverage for durable Gateway-first Agent configuration operations."""

from pathlib import Path
import threading

from fastapi.testclient import TestClient
import pytest

from IM.app import create_app
from IM.application.agent_config_operations import candidate_fingerprint
from IM.infra.repositories.agent_config_operations import (
    AgentConfigOperationRepository,
)
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository

from tests.im_service._auth_helpers import authorize, register_user


def _seed_agent(app, *, owner_id: str, agent_id: str = "agent-1") -> None:
    NodeRepository(app.state.connection).upsert_node(
        node_id="node-1", node_name="MacBook"
    )
    AgentProfileRepository(app.state.connection).upsert_profile(
        agent_id=agent_id,
        owner_id=owner_id,
        node_id="node-1",
        display_name="Alpha",
        description="initial",
        skills=["plan"],
        tool_allowlist=["read"],
        group_reply_policy="manual",
        default_model="model-a",
        reasoning_effort="low",
        workspace_root="/srv/agents/agent-1",
    )


def _update_payload(*, profile_version: int = 1) -> dict[str, object]:
    return {
        "profile_version": profile_version,
        "display_name": "Alpha",
        "description": "updated",
        "skills": ["plan"],
        "tool_allowlist": ["read"],
        "group_reply_policy": "manual",
        "default_model": "model-a",
        "reasoning_effort": "high",
        "features": {},
        "custom_prompt": None,
        "heartbeat": {"every": "30m", "active_hours": None},
    }


def test_pending_apply_recovers_from_status_before_profile_read(tmp_path: Path) -> None:
    """Keep IM old state non-authoritative until status confirms the lost applied ACK."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        _seed_agent(app, owner_id=owner.owner_id)
        captured: dict[str, object] = {}
        apply_operation_ids: list[str] = []

        async def fake_apply(**kwargs):
            apply_operation_ids.append(kwargs["operation_id"])
            captured.update(kwargs)
            return None

        async def pending_status(**kwargs):
            captured["status_operation_id"] = kwargs["operation_id"]
            return {"operation_id": kwargs["operation_id"], "status": "pending"}

        app.state.gateway_control.request_agent_config_apply = fake_apply
        app.state.gateway_control.request_agent_config_operation_status = pending_status
        pending = client.patch("/im/v1/agents/agent-1/config", json=_update_payload())
        assert pending.status_code == 503
        assert pending.json()["detail"]["code"] == "config_apply_pending"
        assert captured["status_operation_id"] == captured["operation_id"]
        assert apply_operation_ids == [captured["operation_id"]] * 2
        stored = AgentProfileRepository(app.state.connection).get_profile(
            agent_id="agent-1"
        )
        assert stored is not None
        assert stored.reasoning_effort == "low"
        assert stored.profile_version == 1

        async def applied_status(**kwargs):
            assert kwargs["operation_id"] == captured["operation_id"]
            return {
                "operation_id": kwargs["operation_id"],
                "status": "applied",
                "candidate_fingerprint": captured["candidate_fingerprint"],
                "agent": captured["payload"],
            }

        app.state.gateway_control.request_agent_config_operation_status = applied_status
        recovered = client.get("/im/v1/agents/agent-1/config?source=mirror")
        assert recovered.status_code == 200
        assert recovered.json()["reasoning_effort"] == "high"
        assert recovered.json()["profile_version"] == 2
        operation = app.state.connection.execute(
            "SELECT status FROM agent_config_operations WHERE operation_id = ?",
            (captured["operation_id"],),
        ).fetchone()
        assert operation["status"] == "committed"


def test_pending_explicit_empty_skills_recovery_preserves_canonical_candidate(
    tmp_path: Path,
) -> None:
    """Keep explicit zero-Skill selection intact across lost-ACK recovery."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        _seed_agent(app, owner_id=owner.owner_id)
        captured: dict[str, object] = {}
        payload = _update_payload()
        payload.update(
            skills=[],
            skills_selection_mode="explicit_allowlist",
        )

        async def lost_apply(**kwargs):
            captured.update(kwargs)
            return None

        async def pending_status(**kwargs):
            return {"operation_id": kwargs["operation_id"], "status": "pending"}

        app.state.gateway_control.request_agent_config_apply = lost_apply
        app.state.gateway_control.request_agent_config_operation_status = pending_status
        pending = client.patch("/im/v1/agents/agent-1/config", json=payload)

        assert pending.status_code == 503
        assert captured["payload"]["skills"] == []
        assert captured["payload"]["skills_selection_mode"] == "explicit_allowlist"
        operation = AgentConfigOperationRepository(app.state.connection).get(
            operation_id=str(captured["operation_id"])
        )
        assert operation is not None
        assert operation.candidate["skills"] == []
        assert operation.candidate["skills_selection_mode"] == "explicit_allowlist"
        assert operation.candidate_fingerprint == candidate_fingerprint(
            operation.candidate
        )
        assert operation.candidate_fingerprint == captured["candidate_fingerprint"]

        async def applied_status(**kwargs):
            return {
                "operation_id": kwargs["operation_id"],
                "status": "applied",
                "candidate_fingerprint": captured["candidate_fingerprint"],
                "agent": captured["payload"],
            }

        app.state.gateway_control.request_agent_config_operation_status = applied_status
        recovered = client.get("/im/v1/agents/agent-1/config?source=mirror")

        assert recovered.status_code == 200
        assert recovered.json()["skills"] == []
        assert recovered.json()["skills_selection_mode"] == "explicit_allowlist"
        assert recovered.json()["profile_version"] == 2
        stored = AgentProfileRepository(app.state.connection).get_profile(
            agent_id="agent-1"
        )
        assert stored is not None
        assert stored.skills == []
        assert stored.skills_selection_mode == "explicit_allowlist"
        committed = AgentConfigOperationRepository(app.state.connection).get(
            operation_id=str(captured["operation_id"])
        )
        assert committed is not None
        assert committed.status == "committed"
        assert committed.candidate["skills"] == []
        assert committed.candidate["skills_selection_mode"] == "explicit_allowlist"


def test_pending_apply_surfaces_recovered_rejection(tmp_path: Path) -> None:
    """Return the recovered Gateway rejection instead of exposing the old profile."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        _seed_agent(app, owner_id=owner.owner_id)

        async def no_result(**kwargs):
            return None

        app.state.gateway_control.request_agent_config_apply = no_result
        app.state.gateway_control.request_agent_config_operation_status = no_result
        assert (
            client.patch(
                "/im/v1/agents/agent-1/config", json=_update_payload()
            ).status_code
            == 503
        )

        async def rejected_status(**kwargs):
            return {
                "operation_id": kwargs["operation_id"],
                "status": "rejected",
                "error_code": "operation_conflict",
            }

        app.state.gateway_control.request_agent_config_operation_status = (
            rejected_status
        )
        response = client.get("/im/v1/agents/agent-1/config?source=mirror")

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "operation_conflict"
        stored = AgentProfileRepository(app.state.connection).get_profile(
            agent_id="agent-1"
        )
        assert stored is not None
        assert stored.profile_version == 1


def test_apply_websocket_frame_correlates_terminal_result(tmp_path: Path) -> None:
    """Route apply result frames by request and operation id before HTTP success."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        _seed_agent(app, owner_id=owner.owner_id)

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-1"],
                        "capabilities": {},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            result: dict[str, object] = {}

            def update() -> None:
                result["response"] = client.patch(
                    "/im/v1/agents/agent-1/config", json=_update_payload()
                )

            worker = threading.Thread(target=update)
            worker.start()
            request = websocket.receive_json()

            assert request["type"] == "agent.config.apply"
            body = request["payload"]
            assert body["operation_id"]
            assert body["candidate_fingerprint"]
            assert body["expected_previous_fingerprint"]
            assert "fingerprint_schema" not in body
            assert body["agent"]["reasoning_effort"] == "high"
            assert body["agent"]["heartbeat_json"] == (
                '{"active_hours":null,"every":"30m"}'
            )
            pending_result = {
                "request_id": body["request_id"],
                "node_id": "node-1",
                "operation_id": body["operation_id"],
                "status": "pending",
                "candidate_fingerprint": body["candidate_fingerprint"],
            }
            websocket.send_json(
                {
                    "type": "agent.config.apply.result",
                    "payload": pending_result,
                }
            )
            assert websocket.receive_json() == {
                "type": "ack",
                "payload": {
                    "message_type": "agent.config.apply.result",
                    "request_id": body["request_id"],
                    "node_id": "node-1",
                },
            }
            status_request = websocket.receive_json()
            assert status_request == {
                "type": "agent.config.operation.status",
                "payload": {
                    "request_id": status_request["payload"]["request_id"],
                    "operation_id": body["operation_id"],
                },
            }
            applied_result = {
                "request_id": status_request["payload"]["request_id"],
                "node_id": "node-1",
                "operation_id": body["operation_id"],
                "status": "applied",
                "candidate_fingerprint": body["candidate_fingerprint"],
                "agent": body["agent"],
            }
            websocket.send_json(
                {
                    "type": "agent.config.operation.status.result",
                    "payload": applied_result,
                }
            )
            assert websocket.receive_json() == {
                "type": "ack",
                "payload": {
                    "message_type": "agent.config.operation.status.result",
                    "request_id": status_request["payload"]["request_id"],
                    "node_id": "node-1",
                },
            }
            worker.join(timeout=5)

            response = result["response"]
            assert response.status_code == 200
            assert response.json()["reasoning_effort"] == "high"


def test_rejected_apply_returns_safe_conflict_and_keeps_profile(tmp_path: Path) -> None:
    """Map current-catalog rejection to a stable API code without persisting draft state."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        _seed_agent(app, owner_id=owner.owner_id)

        async def rejected_apply(**kwargs):
            return {
                "operation_id": kwargs["operation_id"],
                "status": "rejected",
                "error_code": "invalid_agent_config",
                "message": "internal catalog diagnostic that is not exposed",
            }

        app.state.gateway_control.request_agent_config_apply = rejected_apply
        response = client.patch("/im/v1/agents/agent-1/config", json=_update_payload())

        assert response.status_code == 409
        assert response.json()["detail"] == {
            "code": "invalid_agent_config",
            "message": "The Gateway rejected this configuration; refresh capabilities and choose again.",
        }
        assert "internal catalog" not in response.text
        stored = AgentProfileRepository(app.state.connection).get_profile(
            agent_id="agent-1"
        )
        assert stored is not None
        assert stored.reasoning_effort == "low"
        assert stored.profile_version == 1


def test_im_cas_loss_recovers_compensation_before_conflict(tmp_path: Path) -> None:
    """Recover the concurrent IM winner before reporting the version conflict."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        _seed_agent(app, owner_id=owner.owner_id)
        calls: list[dict[str, object]] = []
        payload = _update_payload()
        payload.update(
            skills=[],
            skills_selection_mode="explicit_allowlist",
        )

        async def applied_with_concurrent_im_write(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                AgentProfileRepository(app.state.connection).update_profile(
                    agent_id="agent-1",
                    profile_version=1,
                    display_name="Concurrent winner",
                    description="winner",
                    skills=[],
                    skills_selection_mode="explicit_allowlist",
                    tool_allowlist=["read"],
                    group_reply_policy="manual",
                    default_model="model-a",
                    reasoning_effort="low",
                )
            if len(calls) == 2:
                return None
            return {
                "operation_id": kwargs["operation_id"],
                "status": "applied",
                "candidate_fingerprint": kwargs["candidate_fingerprint"],
                "agent": kwargs["payload"],
            }

        app.state.gateway_control.request_agent_config_apply = (
            applied_with_concurrent_im_write
        )
        response = client.patch("/im/v1/agents/agent-1/config", json=payload)

        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "config_apply_pending"
        assert len(calls) == 2
        assert calls[0]["payload"]["skills"] == []
        assert calls[0]["payload"]["skills_selection_mode"] == "explicit_allowlist"
        assert calls[1]["payload"]["display_name"] == "Concurrent winner"
        assert calls[1]["payload"]["skills"] == []
        assert calls[1]["payload"]["skills_selection_mode"] == "explicit_allowlist"
        assert (
            calls[1]["expected_previous_fingerprint"]
            == calls[0]["candidate_fingerprint"]
        )
        compensation = AgentConfigOperationRepository(app.state.connection).get_active(
            agent_id="agent-1", owner_id=owner.owner_id
        )
        assert compensation is not None
        assert compensation.operation_kind == "compensation"
        assert compensation.candidate["skills"] == []
        assert compensation.candidate["skills_selection_mode"] == "explicit_allowlist"
        assert compensation.candidate_fingerprint == candidate_fingerprint(
            compensation.candidate
        )
        assert compensation.candidate_fingerprint == calls[1]["candidate_fingerprint"]

        async def applied_status(**kwargs):
            assert kwargs["operation_id"] == calls[1]["operation_id"]
            return {
                "operation_id": kwargs["operation_id"],
                "status": "applied",
                "candidate_fingerprint": calls[1]["candidate_fingerprint"],
                "agent": calls[1]["payload"],
            }

        app.state.gateway_control.request_agent_config_operation_status = applied_status
        recovered = client.get("/im/v1/agents/agent-1/config?source=mirror")
        assert recovered.status_code == 409
        assert recovered.json()["detail"]["code"] == "profile_version_conflict"
        stored = AgentProfileRepository(app.state.connection).get_profile(
            agent_id="agent-1"
        )
        assert stored is not None
        assert stored.display_name == "Concurrent winner"
        assert stored.skills == []
        assert stored.skills_selection_mode == "explicit_allowlist"
        assert stored.reasoning_effort == "low"
        assert stored.profile_version == 2
        committed_compensation = AgentConfigOperationRepository(
            app.state.connection
        ).get(operation_id=str(calls[1]["operation_id"]))
        assert committed_compensation is not None
        assert committed_compensation.status == "committed"
        statuses = [
            row["status"]
            for row in app.state.connection.execute(
                "SELECT status FROM agent_config_operations ORDER BY rowid"
            ).fetchall()
        ]
        assert statuses == ["rejected", "committed"]


def test_pending_create_recovers_applied_canonical_agent(tmp_path: Path) -> None:
    """Create the IM profile from status after the original Gateway ACK is lost."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1", node_name="MacBook"
        )
        captured: dict[str, object] = {}

        async def lost_create(**kwargs):
            captured.update(kwargs)
            return None

        async def unknown_status(**kwargs):
            return None

        app.state.gateway_control.request_agent_create = lost_create
        app.state.gateway_control.request_agent_config_operation_status = unknown_status
        payload = {
            "agent_id": "agent-new",
            "owner_id": owner.owner_id,
            "display_name": "New Agent",
            "description": "new",
            "skills": [],
            "tool_allowlist": [],
            "group_reply_policy": "manual",
            "default_model": "model-a",
            "reasoning_effort": "high",
        }
        pending = client.post("/im/v1/nodes/node-1/agents", json=payload)
        assert pending.status_code == 503

        async def applied_status(**kwargs):
            agent = dict(captured["payload"])
            agent["workspace_root"] = "/srv/agents/agent-new"
            return {
                "operation_id": kwargs["operation_id"],
                "status": "applied",
                "candidate_fingerprint": captured["candidate_fingerprint"],
                "agent": agent,
            }

        app.state.gateway_control.request_agent_config_operation_status = applied_status
        recovered = client.post("/im/v1/nodes/node-1/agents", json=payload)

        assert recovered.status_code == 201
        assert recovered.json()["workspace_root"] == "/srv/agents/agent-new"
        assert recovered.json()["reasoning_effort"] == "high"
