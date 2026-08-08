"""Agent creation immutability, recovery, and validation contracts."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

from fastapi.testclient import TestClient
import pytest

from IM.app import create_app
from IM.application.config_service import ConfigService
from IM.infra.repositories.nodes import NodeRepository
from tests.im_service._auth_helpers import authorize, register_user


@pytest.mark.parametrize(
    "code",
    [
        "workspace_parent_missing",
        "workspace_parent_unusable",
        "workspace_target_not_directory",
        "workspace_initialization_failed",
    ],
)
def test_agent_create_maps_workspace_validation_errors_to_422_without_im_writes(
    tmp_path: Path,
    code: str,
) -> None:
    """Stable node-local path failures never create an IM profile or Agent user."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1", node_name="MacBook", owner_id=owner.owner_id
        )

        async def fake_request_agent_create(**_kwargs):
            return {"error": {"code": code, "detail": f"node rejected: {code}"}}

        app.state.gateway_control.request_agent_create = fake_request_agent_create
        response = client.post(
            "/im/v1/nodes/node-1/agents",
            json={
                "agent_id": "agent-invalid",
                "owner_id": "",
                "display_name": "Invalid Workspace",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "MENTION",
                "workspace_root": "/remote/path",
            },
        )

        assert response.status_code == 422
        assert response.json() == {
            "code": code,
            "detail": f"node rejected: {code}",
        }
        assert app.state.connection.execute(
            "SELECT 1 FROM agent_profiles WHERE agent_id = ?", ("agent-invalid",)
        ).fetchone() is None
        assert app.state.connection.execute(
            "SELECT 1 FROM users WHERE username = ?", ("agent:agent-invalid",)
        ).fetchone() is None


def test_ui_shaped_duplicate_create_keeps_authenticated_owner_and_first_root(
    tmp_path: Path,
) -> None:
    """Empty client owner text cannot recreate an existing Agent or move its root."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1", node_name="MacBook", owner_id=owner.owner_id
        )
        gateway_calls: list[str] = []

        async def fake_request_agent_create(**_kwargs):
            root = f"/srv/agents/root-{len(gateway_calls) + 1}"
            gateway_calls.append(root)
            return {
                "agent_id": "fixed-agent",
                "display_name": "Fixed Agent",
                "workspace_root": root,
                "workspace_is_default": False,
            }

        app.state.gateway_control.request_agent_create = fake_request_agent_create
        payload = {
            "agent_id": "fixed-agent",
            "owner_id": "",
            "display_name": "Fixed Agent",
            "skills": [],
            "tool_allowlist": [],
            "group_reply_policy": "MENTION",
            "workspace_root": "/srv/agents/root-1",
        }

        first = client.post("/im/v1/nodes/node-1/agents", json=payload)
        second = client.post(
            "/im/v1/nodes/node-1/agents",
            json={**payload, "workspace_root": "/srv/agents/root-2"},
        )

        assert first.status_code == 201
        assert first.json()["owner_id"] == owner.owner_id
        assert second.status_code == 409
        assert second.json() == {"detail": "agent_id already exists"}
        assert gateway_calls == ["/srv/agents/root-1"]
        stored = app.state.connection.execute(
            "SELECT owner_id, workspace_root FROM agent_profiles WHERE agent_id = ?",
            ("fixed-agent",),
        ).fetchone()
        assert stored is not None
        assert dict(stored) == {
            "owner_id": owner.owner_id,
            "workspace_root": "/srv/agents/root-1",
        }


def test_create_recovers_when_gateway_succeeded_before_im_profile_write_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A same-root retry can complete the missing IM mirror after a lost response."""
    app = create_app(db_path=tmp_path / "im.db")
    original_create_profile = ConfigService.create_profile
    profile_attempts = 0

    def fail_first_profile_write(self, **kwargs):
        nonlocal profile_attempts
        profile_attempts += 1
        if profile_attempts == 1:
            raise ValueError("simulated IM profile write failure")
        return original_create_profile(self, **kwargs)

    monkeypatch.setattr(ConfigService, "create_profile", fail_first_profile_write)
    with TestClient(app) as client:
        owner = register_user(client, username="owner-retry")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-retry", node_name="MacBook", owner_id=owner.owner_id
        )
        gateway_calls = 0

        async def fake_request_agent_create(**_kwargs):
            nonlocal gateway_calls
            gateway_calls += 1
            return {
                "agent_id": "retry-agent",
                "display_name": "Retry Agent",
                "workspace_root": "/srv/agents/retry-agent",
                "workspace_is_default": False,
            }

        app.state.gateway_control.request_agent_create = fake_request_agent_create
        payload = {
            "agent_id": "retry-agent",
            "owner_id": "",
            "display_name": "Retry Agent",
            "skills": [],
            "tool_allowlist": [],
            "group_reply_policy": "MENTION",
            "workspace_root": "/srv/agents/retry-agent",
        }

        failed = client.post("/im/v1/nodes/node-retry/agents", json=payload)
        retried = client.post("/im/v1/nodes/node-retry/agents", json=payload)

        assert failed.status_code == 422
        assert retried.status_code == 201
        assert retried.json()["workspace_root"] == "/srv/agents/retry-agent"
        assert retried.json()["owner_id"] == owner.owner_id
        assert gateway_calls == 2


def test_concurrent_duplicate_http_creates_dispatch_only_one_gateway_create(
    tmp_path: Path,
) -> None:
    """Serialize duplicate create checks before any divergent Gateway side effect."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner-concurrent")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-concurrent", node_name="MacBook", owner_id=owner.owner_id
        )
        gateway_calls: list[str] = []

        async def fake_request_agent_create(*, payload, **_kwargs):
            gateway_calls.append(str(payload["workspace_root"]))
            await asyncio.sleep(0.05)
            return {
                "agent_id": "race-agent",
                "display_name": "Race Agent",
                "workspace_root": payload["workspace_root"],
                "workspace_is_default": False,
            }

        app.state.gateway_control.request_agent_create = fake_request_agent_create
        start = threading.Barrier(3)

        def create(root: str):
            start.wait(timeout=2)
            return client.post(
                "/im/v1/nodes/node-concurrent/agents",
                json={
                    "agent_id": "race-agent",
                    "owner_id": "",
                    "display_name": "Race Agent",
                    "skills": [],
                    "tool_allowlist": [],
                    "group_reply_policy": "MENTION",
                    "workspace_root": root,
                },
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(create, "/srv/agents/race-1"),
                executor.submit(create, "/srv/agents/race-2"),
            ]
            start.wait(timeout=2)
            responses = [future.result(timeout=3) for future in futures]

        assert sorted(response.status_code for response in responses) == [201, 409]
        assert len(gateway_calls) == 1
        stored = app.state.connection.execute(
            "SELECT workspace_root FROM agent_profiles WHERE agent_id = ?",
            ("race-agent",),
        ).fetchone()
        assert stored is not None
        assert stored["workspace_root"] == gateway_calls[0]


def test_agent_create_accepts_target_gateway_workspace_syntax(
    tmp_path: Path,
) -> None:
    """IM persists a successful Gateway root without applying the IM host's path rules."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner-windows")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-windows", node_name="Windows Gateway", owner_id=owner.owner_id
        )

        async def fake_request_agent_create(**_kwargs):
            return {
                "agent_id": "windows-agent",
                "display_name": "Windows Agent",
                "workspace_root": r"C:\\Gateway Data\\windows-agent",
                "workspace_is_default": False,
            }

        app.state.gateway_control.request_agent_create = fake_request_agent_create
        response = client.post(
            "/im/v1/nodes/node-windows/agents",
            json={
                "agent_id": "windows-agent",
                "owner_id": "",
                "display_name": "Windows Agent",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "MENTION",
                "workspace_root": r"C:\\Gateway Data\\windows-agent",
            },
        )

        assert response.status_code == 201, response.text
        assert response.json()["workspace_root"] == r"C:\\Gateway Data\\windows-agent"


def test_agent_create_claims_matching_ownerless_registration_seed_after_lost_response(
    tmp_path: Path,
) -> None:
    """A same-root/name retry can finalize the real Gateway registration seed only."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner-seed")
        authorize(client, owner)
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-seed",
                        "node_name": "Gateway",
                        "version": "1.0.0",
                        "agents": ["seed-agent"],
                        "agent_workspaces": {"seed-agent": "/gateway/seed-agent"},
                        "agent_workspace_is_default": {"seed-agent": False},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            async def fake_request_agent_create(**kwargs):
                requested = kwargs["payload"]
                root = requested["workspace_root"]
                return {
                    "agent_id": "seed-agent",
                    "display_name": "Seed Agent",
                    "description": "Created before the response was lost.",
                    "workspace_root": root,
                    "workspace_is_default": False,
                }

            app.state.gateway_control.request_agent_create = fake_request_agent_create
            payload = {
                "agent_id": "seed-agent",
                "owner_id": "",
                "display_name": "Seed Agent",
                "description": "Created before the response was lost.",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "MENTION",
                "workspace_root": "/gateway/seed-agent",
            }
            changed_root = client.post(
                "/im/v1/nodes/node-seed/agents",
                json={**payload, "workspace_root": "/gateway/other"},
            )
            changed_name = client.post(
                "/im/v1/nodes/node-seed/agents",
                json={**payload, "display_name": "Other Name"},
            )
            claimed = client.post("/im/v1/nodes/node-seed/agents", json=payload)

        assert changed_root.status_code == 409
        assert changed_name.status_code == 409
        assert claimed.status_code == 201, claimed.text
        assert claimed.json()["owner_id"] == owner.owner_id
        assert claimed.json()["display_name"] == "Seed Agent"
        stored = app.state.connection.execute(
            "SELECT owner_id, display_name, description, workspace_root, workspace_is_default "
            "FROM agent_profiles WHERE agent_id = ?",
            ("seed-agent",),
        ).fetchone()
        assert dict(stored) == {
            "owner_id": owner.owner_id,
            "display_name": "Seed Agent",
            "description": "Created before the response was lost.",
            "workspace_root": "/gateway/seed-agent",
            "workspace_is_default": 0,
        }
