"""Integration tests for IM agent configuration APIs."""

from pathlib import Path
import threading

import pytest
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository
from IM.infra.repositories.users import UserRepository

from .conftest import authorize, register_user

# resolve() 与实现侧的 realpath 规范化(feat-388 路径治理)同口径:macOS 上 /tmp 是
# /private/tmp 的符号链接,API 回显规范化路径,期望值不 resolve 则仅 Linux 上成立。
_WORKSPACE_PATH_SETTING = str(Path("/tmp/nano-test/workspace/test-agent").resolve())


def test_get_agent_config_prefers_live_gateway_snapshot(tmp_path: Path) -> None:
    """Read agent config through the connected gateway so IM cache becomes a mirror, not the runtime source."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
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
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
            custom_prompt="cached prompt",
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-1", "agent-1"),
        )
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
                        "node_id": "node-1",
                        "request_id": request_id,
                        "agent_id": "agent-1",
                        "agent": {
                            "display_name": "Live Alpha",
                            "custom_prompt": "stale live prompt",
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
        assert response.json()["custom_prompt"] == "cached prompt"
        assert "system_prompt" not in response.json()
        assert response.json()["skills"] == ["plan"]
        assert response.json()["tool_allowlist"] == ["read"]
        assert response.json()["group_reply_policy"] == "auto"
        assert response.json()["default_model"] == "claude-sonnet-4"
        assert response.json()["workspace_root"] == _WORKSPACE_PATH_SETTING
        assert response.json()["owner_id"] == owner.owner_id
        assert response.json()["profile_version"] == 1


def test_get_agent_config_ignores_mismatched_live_agent_payload(
    tmp_path: Path,
) -> None:
    """A live payload for another agent must not overwrite the requested profile view."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        profiles = AgentProfileRepository(app.state.connection)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1",
            node_name="MacBook",
            status="online",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles.upsert_profile(
            agent_id="default-agent",
            owner_id=owner.owner_id,
            display_name="Default Agent",
            description="cached",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root="/tmp/default-agent",
        )
        profiles.upsert_profile(
            agent_id="luban",
            owner_id=owner.owner_id,
            display_name="Luban",
            description="cached",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root="/tmp/luban",
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id IN (?, ?)",
            ("node-1", "default-agent", "luban"),
        )
        app.state.connection.commit()

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["default-agent", "luban"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            result: dict[str, object] = {}

            def _fetch() -> None:
                result["response"] = client.get("/im/v1/agents/default-agent/config")

            worker = threading.Thread(target=_fetch)
            worker.start()
            request_frame = websocket.receive_json()
            assert request_frame["type"] == "agent.config.get"
            request_id = request_frame["payload"]["request_id"]
            assert request_frame["payload"]["agent_id"] == "default-agent"
            websocket.send_json(
                {
                    "type": "agent.config",
                    "payload": {
                        "node_id": "node-1",
                        "request_id": request_id,
                        "agent_id": "default-agent",
                        "agent": {
                            "agent_id": "luban",
                            "display_name": "Luban",
                            "custom_prompt": "luban prompt",
                            "skills": ["wrong"],
                            "tool_allowlist": ["skill_view"],
                            "group_reply_policy": "auto",
                            "default_model": "wrong-model",
                            "workspace_root": "/tmp/luban",
                        },
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            worker.join(timeout=5)

        response = result["response"]
        assert response.status_code == 200
        body = response.json()
        assert body["agent_id"] == "default-agent"
        assert body["display_name"] == "Default Agent"
        assert (
            Path(body["workspace_root"]).resolve()
            == Path("/tmp/default-agent").resolve()
        )
        assert body["skills"] == []


def test_profile_updates_only_affect_new_conversations(tmp_path: Path) -> None:
    """Snapshot alias-backed direct conversations so old threads stay old and new threads pick up updates."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-1",
            owner_id=owner.owner_id,
            display_name="Alpha",
            description="initial",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )

        agent_participant = users.create_user(
            username="agent:agent-1", display_name="Alpha Alias"
        )
        app.state.connection.execute(
            "UPDATE users SET owner_id = ? WHERE id = ?",
            (owner.owner_id, agent_participant.id),
        )
        app.state.connection.commit()

        first_conv = client.post(
            "/im/v1/conversations",
            json={
                "title": "first",
                "participant_ids": [owner.id, agent_participant.id],
            },
        )
        assert first_conv.status_code == 201
        assert first_conv.json()["config_profile_version"] == 1

        patch_resp = client.patch(
            "/im/v1/agents/agent-1/config",
            json={
                "profile_version": 1,
                "display_name": "Alpha v2",
                "description": "updated",
                "custom_prompt": "v2",
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
            json={
                "title": "second",
                "participant_ids": [owner.id, agent_participant.id],
            },
        )
        assert second_conv.status_code == 201

        first_conv_after_patch = client.get(
            f"/im/v1/conversations/{first_conv.json()['id']}"
        )
        second_conv_after_patch = client.get(
            f"/im/v1/conversations/{second_conv.json()['id']}"
        )
        assert first_conv_after_patch.status_code == 200
        assert second_conv_after_patch.status_code == 200
        assert first_conv.json()["config_profile_version"] == 1
        assert first_conv_after_patch.json()["config_profile_version"] == 1
        assert second_conv.json()["config_profile_version"] == 2
        assert second_conv_after_patch.json()["config_profile_version"] == 2


def test_bound_agent_survives_fresh_reregistration_and_remains_updatable(
    tmp_path: Path,
) -> None:
    """Fresh runtime re-registration must not clear ownership from a previously bound agent profile."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        profiles = AgentProfileRepository(app.state.connection)

        nodes.upsert_node(
            node_id="node-fresh",
            node_name="Fresh Runtime",
            status="online",
            version="1.0.0",
        )
        profiles.upsert_profile(
            agent_id="agent-m170-alpha",
            owner_id="",
            display_name="Alpha",
            description="fresh runtime agent",
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

        start_resp = client.post(
            "/im/v1/bind", json={"action": "start", "node_id": "node-fresh"}
        )
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
                "custom_prompt": "Return NO_REPLY.",
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


# ---------------------------------------------------------------------------
# feat-394-M13: cron jobs and heartbeat-md routes must go via WS RPC
# ---------------------------------------------------------------------------


def test_list_cron_jobs_returns_gateway_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return cron jobs delivered by the target node through Gateway RPC."""
    from IM.ws.gateway.control import GatewayControl

    async def _fake_cron_jobs(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> list:
        return [
            {
                "id": "job-rpc-1",
                "name": "via-rpc",
                "schedule": {"kind": "every", "every": "1h"},
                "instruction": "do something",
                "enabled": True,
                "delete_after_run": False,
            }
        ]

    monkeypatch.setattr(GatewayControl, "request_node_cron_jobs", _fake_cron_jobs)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-1",
            node_name="MacBook",
            status="online",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-cron",
            owner_id=owner.owner_id,
            display_name="CronAgent",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=str(tmp_path / "ws"),
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-1", "agent-cron"),
        )
        app.state.connection.commit()

        resp = client.get("/im/v1/agents/agent-cron/cron/jobs")

    assert resp.status_code == 200, resp.text
    jobs = resp.json()
    assert len(jobs) == 1
    assert jobs[0]["id"] == "job-rpc-1"
    assert jobs[0]["name"] == "via-rpc"


def test_list_cron_jobs_returns_empty_when_node_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /im/v1/agents/{id}/cron/jobs returns [] when node is offline (RPC → None)."""
    from IM.ws.gateway.control import GatewayControl

    async def _offline_rpc(
        self, *, target_node_id, agent_id, workspace_root, timeout_seconds=10.0
    ) -> None:
        return None  # node offline / timeout

    monkeypatch.setattr(GatewayControl, "request_node_cron_jobs", _offline_rpc)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner2", display_name="Owner2")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-2",
            node_name="Node2",
            status="offline",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-offline",
            owner_id=owner.owner_id,
            display_name="OffAgent",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=str(tmp_path / "ws2"),
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-2", "agent-offline"),
        )
        app.state.connection.commit()

        resp = client.get("/im/v1/agents/agent-offline/cron/jobs")

    assert resp.status_code == 200
    assert resp.json() == []


def test_get_skills_usage_returns_gateway_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return skill usage delivered by the target node through Gateway RPC."""
    from IM.ws.gateway.control import GatewayControl

    async def _fake_skills_usage(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object]:
        return {
            "agent_id": agent_id,
            "node_id": target_node_id,
            "skills": [
                {
                    "skill_id": "deploy-check",
                    "name": "deploy-check",
                    "source": "F3",
                    "state": "active",
                    "use_count": 3,
                    "last_used_at": "2026-07-02T10:00:00Z",
                    "session_refs": [
                        {
                            "session_id": "s1",
                            "tool_call_id": "tc1",
                            "timestamp": "2026-07-02T10:00:00Z",
                        }
                    ],
                    "recent_call_keys": ["s1:tc1"],
                    "trend_buckets": [0] * 29 + [1],
                }
            ],
            "heatmap_data": [0] * 29 + [1],
            "health": {
                "created_auto_total": 1,
                "active_auto_total": 1,
                "used_auto_total": 1,
            },
        }

    monkeypatch.setattr(GatewayControl, "request_node_skills_usage", _fake_skills_usage)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="skillowner", display_name="SkillOwner")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-skills",
            node_name="SkillNode",
            status="online",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-skills",
            owner_id=owner.owner_id,
            display_name="SkillAgent",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=str(tmp_path / "skill-ws"),
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-skills", "agent-skills"),
        )
        app.state.connection.commit()

        resp = client.get("/im/v1/agents/agent-skills/skills/usage")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["agent_id"] == "agent-skills"
    assert body["node_id"] == "node-skills"
    assert body["skills"][0]["name"] == "deploy-check"
    assert body["skills"][0]["use_count"] == 3
    assert body["heatmap_data"][-1] == 1
    assert body["health"]["created_auto_total"] == 1


def test_get_skills_usage_reports_offline_when_rpc_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /skills/usage returns 503 when the gateway node is offline."""
    from IM.ws.gateway.control import GatewayControl

    async def _offline_rpc(
        self, *, target_node_id, agent_id, workspace_root, timeout_seconds=10.0
    ) -> None:
        return None

    monkeypatch.setattr(GatewayControl, "request_node_skills_usage", _offline_rpc)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="skilloffline", display_name="Offline")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-skills-offline",
            node_name="SkillOffline",
            status="offline",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-skills-offline",
            owner_id=owner.owner_id,
            display_name="SkillOffline",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=str(tmp_path / "skill-ws-offline"),
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-skills-offline", "agent-skills-offline"),
        )
        app.state.connection.commit()

        resp = client.get("/im/v1/agents/agent-skills-offline/skills/usage")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "target_node_id is not connected"


def test_delete_cron_job_returns_gateway_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expose a successful cron deletion delivered by Gateway RPC."""
    from IM.ws.gateway.control import GatewayControl

    async def _fake_cron_delete(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        job_id: str,
        timeout_seconds: float = 10.0,
    ) -> bool:
        return True  # job found and deleted

    monkeypatch.setattr(GatewayControl, "request_node_cron_delete", _fake_cron_delete)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner3", display_name="Owner3")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-3",
            node_name="Node3",
            status="online",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-del",
            owner_id=owner.owner_id,
            display_name="DelAgent",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=str(tmp_path / "ws3"),
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-3", "agent-del"),
        )
        app.state.connection.commit()

        resp = client.delete("/im/v1/agents/agent-del/cron/jobs/job-1")

    assert resp.status_code == 204, resp.text


def test_delete_cron_job_returns_404_when_node_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DELETE returns 404 when node is offline (RPC → None)."""
    from IM.ws.gateway.control import GatewayControl

    async def _offline_rpc(
        self, *, target_node_id, agent_id, workspace_root, job_id, timeout_seconds=10.0
    ):
        return None

    monkeypatch.setattr(GatewayControl, "request_node_cron_delete", _offline_rpc)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner4", display_name="Owner4")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-4",
            node_name="Node4",
            status="offline",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-del2",
            owner_id=owner.owner_id,
            display_name="DelAgent2",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=str(tmp_path / "ws4"),
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-4", "agent-del2"),
        )
        app.state.connection.commit()

        resp = client.delete("/im/v1/agents/agent-del2/cron/jobs/job-x")

    assert resp.status_code == 404


def test_get_heartbeat_md_returns_gateway_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return heartbeat content delivered by the target node through Gateway RPC."""
    from IM.ws.gateway.control import GatewayControl

    async def _fake_hb_md(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> str:
        return "# HEARTBEAT\n- Watch CPU daily"

    monkeypatch.setattr(GatewayControl, "request_node_heartbeat_md", _fake_hb_md)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner5", display_name="Owner5")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-5",
            node_name="Node5",
            status="online",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-hb",
            owner_id=owner.owner_id,
            display_name="HbAgent",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=str(tmp_path / "ws5"),
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-5", "agent-hb"),
        )
        app.state.connection.commit()

        resp = client.get("/im/v1/agents/agent-hb/heartbeat-md")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content"] == "# HEARTBEAT\n- Watch CPU daily"


def test_get_heartbeat_md_returns_empty_when_node_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /heartbeat-md returns empty content when node is offline (RPC → None)."""
    from IM.ws.gateway.control import GatewayControl

    async def _offline_rpc(
        self, *, target_node_id, agent_id, workspace_root, timeout_seconds=10.0
    ):
        return None

    monkeypatch.setattr(GatewayControl, "request_node_heartbeat_md", _offline_rpc)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner6", display_name="Owner6")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-6",
            node_name="Node6",
            status="offline",
            version="1.0.0",
            owner_id=owner.owner_id,
        )
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-hb2",
            owner_id=owner.owner_id,
            display_name="HbAgent2",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=str(tmp_path / "ws6"),
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-6", "agent-hb2"),
        )
        app.state.connection.commit()

        resp = client.get("/im/v1/agents/agent-hb2/heartbeat-md")

    assert resp.status_code == 200
    assert resp.json()["content"] == ""
    assert resp.json()["node_online"] is False
