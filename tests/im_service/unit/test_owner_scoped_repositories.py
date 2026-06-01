"""Unit tests for owner-scoped repository read paths (tenant isolation contract).

The IM repository layer must enforce ``WHERE owner_id = ?`` for every list/get
performed from inside an API route. These tests pin the contract directly at
the repository level so it cannot be silently broken by callers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    AgentProfileRepository,
    ConversationRepository,
    MessageRepository,
    NodeRepository,
    UserRepository,
)


@pytest.fixture()
def repos(
    tmp_path: Path,
) -> tuple[
    UserRepository,
    ConversationRepository,
    MessageRepository,
    AgentProfileRepository,
    NodeRepository,
]:
    """Build a populated repository graph for two distinct owners (A and B)."""
    connection = connect(tmp_path / "im.sqlite3")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    profiles = AgentProfileRepository(connection)
    nodes = NodeRepository(connection)
    return users, conversations, messages, profiles, nodes


def test_list_conversations_for_owner_returns_only_owner_rows(repos) -> None:
    """list_conversations_for_owner must return only conversations owned by the caller."""
    users, conversations, messages, _, _ = repos
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    conversations.create_conversation(title="A-only", participant_ids=[alice.id])
    conversations.create_conversation(title="B-only", participant_ids=[bob.id])

    alice_visible = conversations.list_conversations_for_owner(owner_id=alice.owner_id)
    bob_visible = conversations.list_conversations_for_owner(owner_id=bob.owner_id)

    assert {item.title for item in alice_visible} == {"A-only"}
    assert {item.title for item in bob_visible} == {"B-only"}


def test_get_conversation_for_owner_returns_none_for_other_owner(repos) -> None:
    """get_conversation_for_owner must hide existence of conversations owned by others (return None)."""
    users, conversations, _, _, _ = repos
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    bob_conv = conversations.create_conversation(
        title="B-only", participant_ids=[bob.id]
    )

    assert (
        conversations.get_conversation_for_owner(
            conversation_id=bob_conv.id,
            owner_id=alice.owner_id,
        )
        is None
    )
    assert (
        conversations.get_conversation_for_owner(
            conversation_id=bob_conv.id,
            owner_id=bob.owner_id,
        )
        is not None
    )


def test_list_runtime_selectable_profiles_for_owner_filters(repos) -> None:
    """Agents listed must be owner-scoped (no cross-owner leakage)."""
    users, _, _, profiles, nodes = repos
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    nodes.upsert_node(
        node_id="node-A",
        owner_id=alice.owner_id,
        node_name="Alice Mac",
        version="1.0.0",
    )
    nodes.upsert_node(
        node_id="node-B", owner_id=bob.owner_id, node_name="Bob Mac", version="1.0.0"
    )
    profiles.upsert_profile(
        agent_id="agent-A",
        owner_id=alice.owner_id,
        node_id="node-A",
        display_name="A Bot",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root="/tmp/a",
    )
    profiles.upsert_profile(
        agent_id="agent-B",
        owner_id=bob.owner_id,
        node_id="node-B",
        display_name="B Bot",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root="/tmp/b",
    )

    alice_agents = profiles.list_runtime_selectable_profiles_for_owner(
        owner_id=alice.owner_id
    )
    bob_agents = profiles.list_runtime_selectable_profiles_for_owner(
        owner_id=bob.owner_id
    )
    assert [item.agent_id for item in alice_agents] == ["agent-A"]
    assert [item.agent_id for item in bob_agents] == ["agent-B"]


def test_get_profile_for_owner_returns_none_for_other_owner(repos) -> None:
    """get_profile_for_owner must hide profiles belonging to another owner."""
    users, _, _, profiles, _ = repos
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    profiles.upsert_profile(
        agent_id="agent-B",
        owner_id=bob.owner_id,
        node_id="node-B",
        display_name="B Bot",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root="/tmp/b",
    )
    assert (
        profiles.get_profile_for_owner(agent_id="agent-B", owner_id=alice.owner_id)
        is None
    )
    assert (
        profiles.get_profile_for_owner(agent_id="agent-B", owner_id=bob.owner_id)
        is not None
    )


def test_list_nodes_for_owner_filters(repos) -> None:
    """list_nodes_for_owner must return only nodes whose owner_id matches."""
    users, _, _, _, nodes = repos
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    nodes.upsert_node(
        node_id="node-A",
        owner_id=alice.owner_id,
        node_name="Alice's Mac",
        version="1.0.0",
    )
    nodes.upsert_node(
        node_id="node-B",
        owner_id=bob.owner_id,
        node_name="Bob's Mac",
        version="1.0.0",
    )

    alice_visible = nodes.list_nodes_for_owner(owner_id=alice.owner_id)
    bob_visible = nodes.list_nodes_for_owner(owner_id=bob.owner_id)
    assert {item.node_id for item in alice_visible} == {"node-A"}
    assert {item.node_id for item in bob_visible} == {"node-B"}
