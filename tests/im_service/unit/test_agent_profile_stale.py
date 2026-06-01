"""Unit tests for ghost-agent reconcile on Gateway register (bugfix-362-M1).

Covers:
- AgentProfileRepository.mark_stale_for_node: empty / partial advertise / revive
- list_runtime_selectable_profiles[_for_owner] filters stale rows
- DB migration idempotency for is_stale / staled_at columns
"""

from __future__ import annotations

from pathlib import Path

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import AgentProfileRepository, NodeRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upsert(
    profiles: AgentProfileRepository, *, agent_id: str, node_id: str, owner_id: str = ""
) -> None:
    profiles.upsert_profile(
        agent_id=agent_id,
        owner_id=owner_id,
        node_id=node_id,
        display_name=agent_id,
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root="/tmp/ws",
    )


@pytest.fixture()
def repos(tmp_path: Path) -> tuple[AgentProfileRepository, NodeRepository]:
    connection = connect(tmp_path / "im.sqlite3")
    initialize_schema(connection)
    profiles = AgentProfileRepository(connection)
    nodes = NodeRepository(connection)
    return profiles, nodes


# ---------------------------------------------------------------------------
# mark_stale_for_node – empty advertise
# ---------------------------------------------------------------------------


def test_mark_stale_for_node_empty_advertise_marks_all(repos) -> None:
    """When agents=[] all active profiles for that node become stale."""
    profiles, nodes = repos
    nodes.upsert_node(node_id="N", owner_id="", node_name="N", version="1")
    _upsert(profiles, agent_id="A", node_id="N")
    _upsert(profiles, agent_id="B", node_id="N")

    count = profiles.mark_stale_for_node(node_id="N", advertised_agent_ids=[])
    assert count == 2
    a = profiles.get_profile(agent_id="A")
    b = profiles.get_profile(agent_id="B")
    assert a is not None and a.is_stale is True
    assert b is not None and b.is_stale is True


# ---------------------------------------------------------------------------
# mark_stale_for_node – non-empty advertise
# ---------------------------------------------------------------------------


def test_mark_stale_for_node_partial_advertise(repos) -> None:
    """Only agents absent from advertised list become stale; listed ones stay active."""
    profiles, nodes = repos
    nodes.upsert_node(node_id="N", owner_id="", node_name="N", version="1")
    _upsert(profiles, agent_id="A", node_id="N")
    _upsert(profiles, agent_id="B", node_id="N")
    _upsert(profiles, agent_id="X", node_id="N")  # ghost – not in new advertise

    count = profiles.mark_stale_for_node(node_id="N", advertised_agent_ids=["A", "B"])
    assert count == 1
    assert profiles.get_profile(agent_id="X").is_stale is True
    assert profiles.get_profile(agent_id="A").is_stale is False
    assert profiles.get_profile(agent_id="B").is_stale is False


def test_mark_stale_for_node_no_change_when_already_stale(repos) -> None:
    """Calling mark_stale_for_node again does not double-count already-stale rows."""
    profiles, nodes = repos
    nodes.upsert_node(node_id="N", owner_id="", node_name="N", version="1")
    _upsert(profiles, agent_id="X", node_id="N")
    profiles.mark_stale_for_node(node_id="N", advertised_agent_ids=[])
    # second call — X is already stale, count should be 0
    count = profiles.mark_stale_for_node(node_id="N", advertised_agent_ids=[])
    assert count == 0


def test_mark_stale_for_node_does_not_touch_other_nodes(repos) -> None:
    """Stale reconcile is per-node; agents on other nodes must not be affected."""
    profiles, nodes = repos
    nodes.upsert_node(node_id="N1", owner_id="", node_name="N1", version="1")
    nodes.upsert_node(node_id="N2", owner_id="", node_name="N2", version="1")
    _upsert(profiles, agent_id="A", node_id="N1")
    _upsert(profiles, agent_id="B", node_id="N2")

    profiles.mark_stale_for_node(node_id="N1", advertised_agent_ids=[])
    assert profiles.get_profile(agent_id="A").is_stale is True
    assert profiles.get_profile(agent_id="B").is_stale is False


# ---------------------------------------------------------------------------
# Revive path: upsert clears stale
# ---------------------------------------------------------------------------


def test_upsert_clears_stale_flag(repos) -> None:
    """upsert_profile on a previously stale agent resets is_stale to False."""
    profiles, nodes = repos
    nodes.upsert_node(node_id="N", owner_id="", node_name="N", version="1")
    _upsert(profiles, agent_id="X", node_id="N")
    profiles.mark_stale_for_node(node_id="N", advertised_agent_ids=[])
    assert profiles.get_profile(agent_id="X").is_stale is True

    # Simulate Gateway restart that re-advertises X
    _upsert(profiles, agent_id="X", node_id="N")
    assert profiles.get_profile(agent_id="X").is_stale is False


# ---------------------------------------------------------------------------
# list_runtime_selectable – stale filter
# ---------------------------------------------------------------------------


def test_list_runtime_selectable_excludes_stale(repos) -> None:
    """list_runtime_selectable_profiles must not return stale agents."""
    profiles, nodes = repos
    nodes.upsert_node(node_id="N", owner_id="", node_name="N", version="1")
    _upsert(profiles, agent_id="A", node_id="N")
    _upsert(profiles, agent_id="X", node_id="N")
    profiles.mark_stale_for_node(node_id="N", advertised_agent_ids=["A"])

    visible = profiles.list_runtime_selectable_profiles()
    assert [p.agent_id for p in visible] == ["A"]


def test_list_runtime_selectable_for_owner_excludes_stale(repos) -> None:
    """list_runtime_selectable_profiles_for_owner must not return stale agents."""
    profiles, nodes = repos
    from IM.infra.repositories import UserRepository
    from IM.infra.db import connect

    # reuse the same connection from repos fixture via the profiles object
    users = UserRepository(profiles._connection)
    alice = users.create_user(username="alice", display_name="Alice")
    nodes.upsert_node(node_id="N", owner_id=alice.owner_id, node_name="N", version="1")

    _upsert(profiles, agent_id="A", node_id="N", owner_id=alice.owner_id)
    _upsert(profiles, agent_id="X", node_id="N", owner_id=alice.owner_id)
    profiles.mark_stale_for_node(node_id="N", advertised_agent_ids=["A"])

    visible = profiles.list_runtime_selectable_profiles_for_owner(
        owner_id=alice.owner_id
    )
    assert [p.agent_id for p in visible] == ["A"]


# ---------------------------------------------------------------------------
# First register on empty node – no-op
# ---------------------------------------------------------------------------


def test_mark_stale_no_op_on_fresh_node(repos) -> None:
    """When the node has no prior agent_profiles, reconcile affects 0 rows."""
    profiles, nodes = repos
    nodes.upsert_node(node_id="N", owner_id="", node_name="N", version="1")
    count = profiles.mark_stale_for_node(node_id="N", advertised_agent_ids=["A", "B"])
    assert count == 0


# ---------------------------------------------------------------------------
# DB migration idempotency
# ---------------------------------------------------------------------------


def test_initialize_schema_idempotent_with_stale_columns(tmp_path: Path) -> None:
    """Calling initialize_schema multiple times must not raise on the new stale columns."""
    connection = connect(tmp_path / "im.sqlite3")
    initialize_schema(connection)
    # second call must succeed without errors
    initialize_schema(connection)
    col_names = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(agent_profiles)").fetchall()
    }
    assert "is_stale" in col_names
    assert "staled_at" in col_names
