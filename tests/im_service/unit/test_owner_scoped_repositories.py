"""Chat reads follow membership while Agent and node management follow ownership."""

from __future__ import annotations

from pathlib import Path

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.nodes import NodeRepository
from IM.infra.repositories.users import UserRepository


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


def test_member_chat_reads_include_shared_groups_and_exclude_other_private_chats(
    repos,
) -> None:
    """A shared group is visible across owners; an unrelated private chat stays absent."""
    users, conversations, messages, _, _ = repos
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    conversations.create_conversation(title="A-only", participant_ids=[alice.id])
    bob_conversation = conversations.create_conversation(
        title="B-only", participant_ids=[bob.id]
    )

    conversations.create_conversation(
        title="Shared",
        participant_ids=[alice.id, bob.id],
        caller_owner_id=alice.id,
        conversation_type="group",
    )

    alice_visible = conversations.list_conversations_for_member(user_id=alice.id)
    bob_visible = conversations.list_conversations_for_member(user_id=bob.id)

    assert {item.title for item in alice_visible} == {"A-only", "Shared"}
    assert {item.title for item in bob_visible} == {"B-only", "Shared"}
    assert (
        conversations.get_conversation_for_member(
            conversation_id=bob_conversation.id,
            user_id=alice.id,
        )
        is None
    )
    assert (
        conversations.get_conversation_for_member(
            conversation_id=bob_conversation.id,
            user_id=bob.id,
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
