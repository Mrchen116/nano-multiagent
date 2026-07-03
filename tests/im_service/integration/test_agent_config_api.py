"""Integration tests for IM agent configuration APIs."""

from pathlib import Path
import threading

import pytest
from fastapi.testclient import TestClient

from IM.api.routes import agents as agent_routes
from IM.app import create_app
from IM.infra.repositories import AgentProfileRepository, NodeRepository, UserRepository

from .conftest import authorize, register_user

# resolve() 与实现侧的 realpath 规范化(feat-388 路径治理)同口径:macOS 上 /tmp 是
# /private/tmp 的符号链接,API 回显规范化路径,期望值不 resolve 则仅 Linux 上成立。
_WORKSPACE_PATH_SETTING = str(Path("/tmp/nano-test/workspace/test-agent").resolve())


def test_agents_list_get_patch_and_conflict(tmp_path: Path) -> None:
    """List runtime-selectable agents, then read and optimistically update one config."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
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
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-1", "agent-1"),
        )
        app.state.connection.commit()

        list_resp = client.get("/im/v1/agents")
        assert list_resp.status_code == 200
        # Use subset assertion: node_status is runtime-derived and may change.
        agent_row = list_resp.json()[0]
        assert {
            k: agent_row[k]
            for k in (
                "agent_id",
                "owner_id",
                "node_id",
                "display_name",
                "description",
                "profile_version",
                "default_model",
                "workspace_is_default",
            )
        } == {
            "agent_id": "agent-1",
            "owner_id": owner.owner_id,
            "node_id": "node-1",
            "display_name": "Alpha",
            "description": "initial",
            "profile_version": 1,
            "default_model": "gpt-4.1",
            "workspace_is_default": True,
        }
        assert list_resp.json()[0]["user_id"] is not None
        assert list_resp.json()[0]["workspace_root"].endswith(
            "/nano-assistant/workspace/agent-1"
        )

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
        assert reset_body["workspace_root"].endswith(
            "/nano-assistant/workspace/agent-1"
        )
        # bugfix-404-M2: update_profile 不写 workspace_root 列——DB 存量为 NULL（
        # 初始 upsert 时 workspace_root=None），API 回显时 workspace_root_for_profile()
        # 派生为 managed default。DB 值本身保持 NULL。
        stored_row = app.state.connection.execute(
            "SELECT workspace_root FROM agent_profiles WHERE agent_id = ?",
            (seeded.agent_id,),
        ).fetchone()
        assert stored_row is not None
        assert stored_row["workspace_root"] is None

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
            system_prompt="cached prompt",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
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
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
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


def test_agents_list_includes_fresh_runtime_profiles_before_bind(
    tmp_path: Path,
) -> None:
    """Fresh gateway runtimes should expose ownerless bound agents before bind confirmation."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        viewer = register_user(client, username="viewer", display_name="Viewer")
        authorize(client, viewer)
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
        # Use subset assertion: node_status is runtime-derived and may change.
        agent_row = response.json()[0]
        assert {
            k: agent_row[k]
            for k in (
                "agent_id",
                "owner_id",
                "node_id",
                "display_name",
                "description",
                "profile_version",
                "default_model",
                "workspace_is_default",
            )
        } == {
            "agent_id": "agent-fresh",
            "owner_id": "",
            "node_id": "node-fresh",
            "display_name": "Fresh Agent",
            "description": "advertised by an unbound runtime",
            "profile_version": 1,
            "default_model": None,
            "workspace_is_default": True,
        }
        assert response.json()[0]["workspace_root"].endswith(
            "/nano-assistant/workspace/agent-fresh"
        )
        assert response.json()[0]["user_id"] is not None


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
            system_prompt="You are Alpha.",
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


def test_node_capabilities_return_current_selectable_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expose current gateway-resolved skill/tool/model items for the settings UI."""

    async def _fake_node_capabilities(
        self, *, target_node_id: str, timeout_seconds: float = 15.0
    ):  # noqa: ARG002
        return {
            "skills": ["plan", "playwright"],
            "tools": ["read", "bash"],
            "models": ["kimiCoding:K2.6", "codex_oauth:gpt-5.5"],
        }

    from IM.ws.gateway_handler import GatewayHandler

    monkeypatch.setattr(
        GatewayHandler, "request_node_capabilities", _fake_node_capabilities
    )

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        viewer = register_user(client, username="viewer", display_name="Viewer")
        authorize(client, viewer)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-1", node_name="MacBook", status="online", version="1.0.0"
        )
        response = client.get("/im/v1/nodes/node-1/capabilities")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["skills"]] == [
        "plan",
        "playwright",
    ]
    assert [item["name"] for item in response.json()["tools"]] == ["read", "bash"]


# ---------------------------------------------------------------------------
# feat-394-M13: cron jobs and heartbeat-md routes must go via WS RPC
# ---------------------------------------------------------------------------


def test_list_cron_jobs_calls_rpc_not_direct_file_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /im/v1/agents/{id}/cron/jobs must use request_node_cron_jobs RPC.

    feat-394-M13 (决策 G): IM must never directly read gateway workspace files.
    The cron jobs list must arrive via the WS RPC path.
    """
    from IM.ws.gateway_handler import GatewayHandler

    rpc_calls: list[dict] = []

    async def _fake_cron_jobs(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> list:
        rpc_calls.append({"target_node_id": target_node_id, "agent_id": agent_id})
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

    monkeypatch.setattr(GatewayHandler, "request_node_cron_jobs", _fake_cron_jobs)

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
            system_prompt="",
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
    # RPC must have been called (not direct file read).
    assert len(rpc_calls) == 1, f"RPC was not called: {rpc_calls!r}"
    assert rpc_calls[0]["agent_id"] == "agent-cron"


def test_list_cron_jobs_returns_empty_when_node_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /im/v1/agents/{id}/cron/jobs returns [] when node is offline (RPC → None)."""
    from IM.ws.gateway_handler import GatewayHandler

    async def _offline_rpc(
        self, *, target_node_id, agent_id, workspace_root, timeout_seconds=10.0
    ) -> None:
        return None  # node offline / timeout

    monkeypatch.setattr(GatewayHandler, "request_node_cron_jobs", _offline_rpc)

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
            system_prompt="",
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


def test_get_skills_usage_calls_rpc_not_direct_file_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /im/v1/agents/{id}/skills/usage must use gateway WS RPC."""
    from IM.ws.gateway_handler import GatewayHandler

    rpc_calls: list[dict[str, str]] = []

    async def _fake_skills_usage(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object]:
        rpc_calls.append(
            {
                "target_node_id": target_node_id,
                "agent_id": agent_id,
                "workspace_root": workspace_root,
            }
        )
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

    monkeypatch.setattr(
        GatewayHandler, "request_node_skills_usage", _fake_skills_usage
    )

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
            system_prompt="",
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
    assert len(rpc_calls) == 1
    assert rpc_calls[0]["agent_id"] == "agent-skills"


def test_get_skills_usage_reports_offline_when_rpc_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /skills/usage returns 503 when the gateway node is offline."""
    from IM.ws.gateway_handler import GatewayHandler

    async def _offline_rpc(
        self, *, target_node_id, agent_id, workspace_root, timeout_seconds=10.0
    ) -> None:
        return None

    monkeypatch.setattr(GatewayHandler, "request_node_skills_usage", _offline_rpc)

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
            system_prompt="",
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


def test_delete_cron_job_calls_rpc_not_direct_file_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DELETE /im/v1/agents/{id}/cron/jobs/{job_id} must use request_node_cron_delete RPC."""
    from IM.ws.gateway_handler import GatewayHandler

    rpc_calls: list[dict] = []

    async def _fake_cron_delete(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        job_id: str,
        timeout_seconds: float = 10.0,
    ) -> bool:
        rpc_calls.append(
            {"target_node_id": target_node_id, "agent_id": agent_id, "job_id": job_id}
        )
        return True  # job found and deleted

    monkeypatch.setattr(GatewayHandler, "request_node_cron_delete", _fake_cron_delete)

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
            system_prompt="",
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
    assert len(rpc_calls) == 1
    assert rpc_calls[0]["job_id"] == "job-1"


def test_delete_cron_job_returns_404_when_node_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DELETE returns 404 when node is offline (RPC → None)."""
    from IM.ws.gateway_handler import GatewayHandler

    async def _offline_rpc(
        self, *, target_node_id, agent_id, workspace_root, job_id, timeout_seconds=10.0
    ):
        return None

    monkeypatch.setattr(GatewayHandler, "request_node_cron_delete", _offline_rpc)

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
            system_prompt="",
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


def test_get_heartbeat_md_calls_rpc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /im/v1/agents/{id}/heartbeat-md must use request_node_heartbeat_md RPC."""
    from IM.ws.gateway_handler import GatewayHandler

    async def _fake_hb_md(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> str:
        return "# HEARTBEAT\n- Watch CPU daily"

    monkeypatch.setattr(GatewayHandler, "request_node_heartbeat_md", _fake_hb_md)

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
            system_prompt="",
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
    from IM.ws.gateway_handler import GatewayHandler

    async def _offline_rpc(
        self, *, target_node_id, agent_id, workspace_root, timeout_seconds=10.0
    ):
        return None

    monkeypatch.setattr(GatewayHandler, "request_node_heartbeat_md", _offline_rpc)

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
            system_prompt="",
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
