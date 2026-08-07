"""Contract tests for opaque Gateway-owned workspace paths in the IM mirror."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository
from tests.im_service._auth_helpers import authorize, register_user


def test_remote_workspace_root_is_never_resolved_or_overwritten_by_live_data(
    tmp_path: Path,
) -> None:
    remote_root = "/tmp/remote-node/agent-opaque"
    seen_roots: list[str] = []
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1", node_name="Remote", owner_id=owner.owner_id
        )
        AgentProfileRepository(app.state.connection).upsert_profile(
            agent_id="agent-1",
            owner_id=owner.owner_id,
            node_id="node-1",
            display_name="Alpha",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="MENTION",
            default_model=None,
            workspace_root=remote_root,
            workspace_is_default=False,
        )

        async def live_config(**_kwargs):
            return {"agent_id": "agent-1", "workspace_root": "/wrong/live/root"}

        async def capabilities(*, workspace_root: str, **_kwargs):
            seen_roots.append(workspace_root)
            return {"models": [], "skills": [], "tools": [], "features": []}

        async def preview(*, workspace_root: str, **_kwargs):
            seen_roots.append(workspace_root)
            return {"prompt": "preview", "section_count": 1}

        async def cron_jobs(*, workspace_root: str, **_kwargs):
            seen_roots.append(workspace_root)
            return []

        async def cron_delete(*, workspace_root: str, **_kwargs):
            seen_roots.append(workspace_root)
            return True

        async def skills_usage(*, workspace_root: str, **_kwargs):
            seen_roots.append(workspace_root)
            return {"skills": [], "heatmap_data": [], "health": {}}

        async def heartbeat(*, workspace_root: str, **_kwargs):
            seen_roots.append(workspace_root)
            return ""

        control = app.state.gateway_control
        control.request_agent_config = live_config
        control.request_agent_capabilities = capabilities
        control.request_prompt_preview = preview
        control.request_node_cron_jobs = cron_jobs
        control.request_node_cron_delete = cron_delete
        control.request_node_skills_usage = skills_usage
        control.request_node_heartbeat_md = heartbeat

        mirror = client.get("/im/v1/agents/agent-1/config?source=mirror")
        live = client.get("/im/v1/agents/agent-1/config?source=live")
        assert mirror.json()["workspace_root"] == remote_root
        assert live.json()["workspace_root"] == remote_root

        assert client.get("/im/v1/agents/agent-1/capabilities").status_code == 200
        assert client.post(
            "/im/v1/agents/agent-1/prompt-preview", json={}
        ).status_code == 200
        assert client.get("/im/v1/agents/agent-1/cron/jobs").status_code == 200
        assert client.delete(
            "/im/v1/agents/agent-1/cron/jobs/job-1"
        ).status_code == 204
        assert client.get("/im/v1/agents/agent-1/skills/usage").status_code == 200
        assert client.get("/im/v1/agents/agent-1/heartbeat-md").status_code == 200

    assert seen_roots == [remote_root] * 6
