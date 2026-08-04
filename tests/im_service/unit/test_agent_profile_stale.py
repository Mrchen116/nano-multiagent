"""Persistence regressions for reconciling stale Gateway agent profiles."""

from pathlib import Path

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository
from IM.infra.repositories.users import UserRepository


def _upsert(
    profiles: AgentProfileRepository,
    *,
    agent_id: str,
    node_id: str,
    owner_id: str = "",
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
def repos(
    tmp_path: Path,
) -> tuple[AgentProfileRepository, NodeRepository, UserRepository]:
    connection = connect(tmp_path / "im.sqlite3")
    initialize_schema(connection)
    return (
        AgentProfileRepository(connection),
        NodeRepository(connection),
        UserRepository(connection),
    )


def test_reconcile_marks_only_missing_node_agents_and_is_idempotent(repos) -> None:
    profiles, nodes, _users = repos
    nodes.upsert_node(node_id="N1", owner_id="", node_name="N1", version="1")
    nodes.upsert_node(node_id="N2", owner_id="", node_name="N2", version="1")
    _upsert(profiles, agent_id="A", node_id="N1")
    _upsert(profiles, agent_id="B", node_id="N1")
    _upsert(profiles, agent_id="other", node_id="N2")

    assert profiles.mark_stale_for_node(node_id="N1", advertised_agent_ids=["A"]) == 1
    assert profiles.get_profile(agent_id="A").is_stale is False
    assert profiles.get_profile(agent_id="B").is_stale is True
    assert profiles.get_profile(agent_id="other").is_stale is False
    assert profiles.mark_stale_for_node(node_id="N1", advertised_agent_ids=["A"]) == 0

    assert profiles.mark_stale_for_node(node_id="N1", advertised_agent_ids=[]) == 1
    assert profiles.get_profile(agent_id="A").is_stale is True
    assert profiles.get_profile(agent_id="other").is_stale is False


def test_reregister_revives_stale_profile(repos) -> None:
    profiles, nodes, _users = repos
    nodes.upsert_node(node_id="N", owner_id="", node_name="N", version="1")
    _upsert(profiles, agent_id="X", node_id="N")
    profiles.mark_stale_for_node(node_id="N", advertised_agent_ids=[])

    _upsert(profiles, agent_id="X", node_id="N")

    assert profiles.get_profile(agent_id="X").is_stale is False


def test_runtime_selectable_lists_exclude_stale_profiles(repos) -> None:
    profiles, nodes, users = repos
    owner = users.create_user(username="alice", display_name="Alice")
    nodes.upsert_node(node_id="N", owner_id=owner.owner_id, node_name="N", version="1")
    _upsert(profiles, agent_id="A", node_id="N", owner_id=owner.owner_id)
    _upsert(profiles, agent_id="X", node_id="N", owner_id=owner.owner_id)
    profiles.mark_stale_for_node(node_id="N", advertised_agent_ids=["A"])

    assert [
        profile.agent_id for profile in profiles.list_runtime_selectable_profiles()
    ] == ["A"]
    assert [
        profile.agent_id
        for profile in profiles.list_runtime_selectable_profiles_for_owner(
            owner_id=owner.owner_id
        )
    ] == ["A"]
