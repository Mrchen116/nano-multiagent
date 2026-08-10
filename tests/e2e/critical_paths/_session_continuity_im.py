"""Real isolated IM subprocess roles for continuity recovery tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import uvicorn

from IM.app import create_app
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository
from IM.infra.repositories.users import UserRepository


def initialize(runtime: Path) -> None:
    """Create the authenticated owner, node, and Agent used by both Gateway rounds."""

    app = create_app(db_path=runtime / "im.sqlite3")
    with TestClient(app) as client:
        response = client.post(
            "/im/v1/auth/register",
            json={
                "username": "continuity",
                "password": "continuity-password",
                "display_name": "Continuity",
                "locale": "en",
            },
        )
        response.raise_for_status()
        payload = response.json()
        user = payload["user"]
        NodeRepository(app.state.connection).record_gateway_registration(
            node_id="node-1",
            node_name="Continuity Node",
            version="test",
            agent_count=1,
            owner_id=user["owner_id"],
        )
        AgentProfileRepository(app.state.connection).upsert_profile(
            agent_id="agent-a",
            owner_id=user["owner_id"],
            node_id="node-1",
            display_name="Agent A",
            description="Continuity recovery agent",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=str(runtime / "workspace"),
        )
        agent_user = UserRepository(app.state.connection).create_user(
            username="agent:agent-a",
            display_name="Agent A",
        )
        app.state.connection.execute(
            "UPDATE users SET owner_id = ? WHERE id = ?",
            (user["owner_id"], agent_user.id),
        )
        app.state.connection.commit()
        print(
            json.dumps(
                {
                    "token": payload["access_token"],
                    "user_id": user["id"],
                    "owner_id": user["owner_id"],
                }
            )
        )


def serve(runtime: Path, *, port: int) -> None:
    """Run the real IM application against the shared test database."""

    uvicorn.run(
        create_app(db_path=runtime / "im.sqlite3"),
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
