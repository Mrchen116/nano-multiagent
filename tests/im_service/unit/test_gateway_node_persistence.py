"""Behavior tests for the concrete Gateway node persistence seam."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.gateway_persistence import GatewayNodePersistence
from IM.infra.repositories import AgentProfileRepository, NodeRepository, UserRepository


def _build(tmp_path: Path) -> tuple[sqlite3.Connection, GatewayNodePersistence]:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return connection, GatewayNodePersistence(connection)


def _register(
    persistence: GatewayNodePersistence,
    *,
    agents: list[str],
    workspaces: dict[str, str] | None = None,
):
    return persistence.register(
        node_id="node-1",
        node_name="Node 1",
        version="v1",
        agent_ids=agents,
        agent_workspaces=workspaces or {},
    )


def test_register_creates_node_profiles_and_agent_users(tmp_path: Path) -> None:
    """First registration persists the advertised runtime facts and typed result."""
    connection, persistence = _build(tmp_path)

    result = _register(
        persistence,
        agents=["agent-a", "plain"],
        workspaces={"agent-a": "/work/a", "plain": "/work/plain"},
    )

    assert result.previous_node is None
    assert result.current_node.status == "online"
    assert result.current_node.agent_count == 2
    assert result.agent_ids == ("agent-a", "plain")
    profiles = AgentProfileRepository(connection)
    assert profiles.get_profile(agent_id="agent-a").display_name == "A"
    assert profiles.get_profile(agent_id="agent-a").workspace_root == "/work/a"
    assert profiles.get_profile(agent_id="plain").display_name == "plain"
    users = UserRepository(connection)
    assert users.get_user_by_username(username="agent:agent-a").display_name == "A"
    assert users.get_user_by_username(username="agent:plain").display_name == "plain"


def test_register_seeds_skills_and_tool_allowlist_on_create(tmp_path: Path) -> None:
    """bugfix-467: first registration seeds skills/tool_allowlist from node.register."""
    connection, persistence = _build(tmp_path)

    result = persistence.register(
        node_id="node-1",
        node_name="Node 1",
        version="v1",
        agent_ids=["agent-a"],
        agent_workspaces={"agent-a": "/work/a"},
        agent_skills={"agent-a": ["plan", "playwright"]},
        agent_tool_allowlist={"agent-a": ["read", "bash", "edit"]},
    )

    assert result.agent_ids == ("agent-a",)
    profiles = AgentProfileRepository(connection)
    profile = profiles.get_profile(agent_id="agent-a")
    assert profile.skills == ["plan", "playwright"]
    assert profile.tool_allowlist == ["read", "bash", "edit"]


def test_register_does_not_overwrite_existing_profile_skills_and_tool_allowlist(
    tmp_path: Path,
) -> None:
    """bugfix-467: re-registration must not clobber user-edited profile values."""
    connection, persistence = _build(tmp_path)
    persistence.register(
        node_id="node-1",
        node_name="Node 1",
        version="v1",
        agent_ids=["agent-a"],
        agent_workspaces={"agent-a": "/work/a"},
        agent_skills={"agent-a": ["plan", "playwright"]},
        agent_tool_allowlist={"agent-a": ["read", "bash", "edit"]},
    )

    # Simulate user clearing skills/tools while Gateway was offline.
    profiles = AgentProfileRepository(connection)
    current = profiles.get_profile(agent_id="agent-a")
    profiles.update_profile(
        agent_id="agent-a",
        profile_version=current.profile_version,
        display_name=current.display_name,
        description=current.description,
        system_prompt=current.system_prompt,
        skills=[],
        tool_allowlist=[],
        group_reply_policy=current.group_reply_policy,
        default_model=current.default_model,
    )

    result = persistence.register(
        node_id="node-1",
        node_name="Node 1",
        version="v1",
        agent_ids=["agent-a"],
        agent_workspaces={"agent-a": "/work/a"},
        agent_skills={"agent-a": ["plan", "playwright"]},
        agent_tool_allowlist={"agent-a": ["read", "bash", "edit"]},
    )

    assert result.agent_ids == ("agent-a",)
    profile = profiles.get_profile(agent_id="agent-a")
    assert profile.skills == [], "existing profile skills must not be re-seeded"
    assert profile.tool_allowlist == [], (
        "existing profile tool_allowlist must not be re-seeded"
    )


def test_reregister_preserves_profile_edits_and_reconciles_stale_agents(
    tmp_path: Path,
) -> None:
    """Re-registration preserves user edits and stales agents no longer advertised."""
    connection, persistence = _build(tmp_path)
    _register(persistence, agents=["agent-a", "agent-old"])
    profiles = AgentProfileRepository(connection)
    current = profiles.get_profile(agent_id="agent-a")
    assert current is not None
    profiles.update_profile(
        agent_id="agent-a",
        profile_version=current.profile_version,
        display_name="Custom A",
        description="Custom description",
        system_prompt="Custom prompt",
        skills=["skill-a"],
        tool_allowlist=["tool-a"],
        group_reply_policy="ALWAYS",
        default_model="model-a",
        features={"heartbeat": True},
        custom_prompt="Custom override",
    )

    result = _register(persistence, agents=["agent-a", "agent-new"])

    assert result.previous_node is not None
    assert result.agent_ids == ("agent-a", "agent-new")
    preserved = profiles.get_profile(agent_id="agent-a")
    assert preserved is not None
    assert preserved.display_name == "Custom A"
    assert preserved.description == "Custom description"
    assert preserved.skills == ["skill-a"]
    assert preserved.features == {"heartbeat": True}
    assert preserved.custom_prompt == "Custom override"
    stale = profiles.get_profile(agent_id="agent-old")
    assert stale is not None and stale.is_stale is True
    fresh = profiles.get_profile(agent_id="agent-new")
    assert fresh is not None and fresh.node_id == "node-1"


def test_register_with_empty_advertisement_marks_all_node_profiles_stale(
    tmp_path: Path,
) -> None:
    """An empty advertised list preserves the node and stales every prior profile."""
    connection, persistence = _build(tmp_path)
    _register(persistence, agents=["agent-a", "agent-b"])

    result = _register(persistence, agents=[])

    assert result.current_node.agent_count == 0
    assert result.agent_ids == ()
    profiles = AgentProfileRepository(connection)
    assert profiles.get_profile(agent_id="agent-a").is_stale is True
    assert profiles.get_profile(agent_id="agent-b").is_stale is True


def test_register_failure_preserves_legacy_durable_rows(tmp_path: Path) -> None:
    """A failure on agent N keeps exactly the writes durable in the legacy sequence."""
    connection, persistence = _build(tmp_path)
    connection.execute(
        """
        CREATE TRIGGER fail_agent_b BEFORE INSERT ON agent_profiles
        WHEN NEW.agent_id = 'agent-b'
        BEGIN SELECT RAISE(FAIL, 'injected agent-b failure'); END
        """
    )
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="injected agent-b failure"):
        _register(
            persistence,
            agents=["agent-a", "agent-b"],
            workspaces={"agent-a": "/a", "agent-b": "/b"},
        )

    nodes = [
        tuple(row)
        for row in connection.execute(
            "SELECT node_id, status, agent_count, version FROM nodes ORDER BY node_id"
        ).fetchall()
    ]
    profiles = [
        tuple(row)
        for row in connection.execute(
            """
            SELECT agent_id, node_id, display_name, workspace_root, is_stale
            FROM agent_profiles ORDER BY agent_id
            """
        ).fetchall()
    ]
    users = [
        tuple(row)
        for row in connection.execute(
            """
            SELECT username, display_name FROM users
            WHERE username LIKE 'agent:%' ORDER BY username
            """
        ).fetchall()
    ]
    assert nodes == [("node-1", "online", 2, "v1")]
    assert profiles == [("agent-a", None, "A", "/a", 0)]
    assert users == [("agent:agent-a", "A")]
    assert connection.in_transaction is False


def test_heartbeat_returns_before_and_after_snapshots(tmp_path: Path) -> None:
    """Heartbeat persists normalized status while exposing transition facts."""
    _, persistence = _build(tmp_path)
    _register(persistence, agents=["agent-a"])

    transition = persistence.heartbeat(
        node_id="node-1",
        reported_status="online",
        agent_count=3,
        last_error="boom",
        version="v2",
    )

    assert transition.previous_node.status == "online"
    assert transition.current_node.status == "degraded"
    assert transition.current_node.agent_count == 3
    assert transition.current_node.last_error == "boom"
    assert transition.agent_ids == ("agent-a",)


def test_disconnect_and_timeout_offline_are_idempotent(tmp_path: Path) -> None:
    """Disconnect and timeout transitions preserve missing/already-offline no-op semantics."""
    _, persistence = _build(tmp_path)
    missing = persistence.mark_offline(node_id="missing", last_error="timeout")
    assert missing.previous_node is None
    assert missing.current_node is None
    assert missing.agent_ids == ()

    _register(persistence, agents=["agent-a"])
    timeout = persistence.mark_offline(node_id="node-1", last_error="heartbeat_timeout")
    assert timeout.previous_node.status == "online"
    assert timeout.current_node.status == "offline"
    assert timeout.current_node.last_error == "heartbeat_timeout"
    assert timeout.agent_ids == ("agent-a",)

    repeated = persistence.mark_offline(node_id="node-1", last_error="new-error")
    assert repeated.previous_node == repeated.current_node
    assert repeated.current_node.last_error == "heartbeat_timeout"


def test_stale_online_node_ids_preserves_legacy_query_iteration_order(
    tmp_path: Path,
) -> None:
    """Stale scan filters by cutoff without imposing a new lexical order."""
    connection, persistence = _build(tmp_path)
    nodes = NodeRepository(connection)
    for node_id in ("node-b", "node-a", "node-fresh"):
        nodes.record_gateway_registration(
            node_id=node_id,
            node_name=node_id,
            version="v1",
            agent_count=0,
        )
    now = datetime.now(timezone.utc)
    stale_at = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    fresh_at = now.isoformat().replace("+00:00", "Z")
    connection.execute(
        "UPDATE nodes SET last_heartbeat_at = ? WHERE node_id IN ('node-a', 'node-b')",
        (stale_at,),
    )
    connection.execute(
        "UPDATE nodes SET last_heartbeat_at = ? WHERE node_id = 'node-fresh'",
        (fresh_at,),
    )
    connection.commit()

    cutoff = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    assert persistence.stale_online_node_ids(cutoff=cutoff) == ("node-b", "node-a")
