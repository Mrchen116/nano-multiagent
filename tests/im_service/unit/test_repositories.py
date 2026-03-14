"""Unit tests for IM repositories backed by SQLite."""

from pathlib import Path

import pytest

from IM.infra.db import connect, initialize_schema
from IM.repositories import (
    AgentProfileRepository,
    AgentProfileVersionConflictError,
    BindRepository,
    ConversationRepository,
    MessageRepository,
    NodeRepository,
    UserRepository,
)


def _build_repositories(
    tmp_path: Path,
) -> tuple[
    UserRepository,
    ConversationRepository,
    MessageRepository,
    AgentProfileRepository,
    NodeRepository,
    BindRepository,
]:
    """Build repository instances bound to a temporary SQLite database."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return (
        UserRepository(connection),
        ConversationRepository(connection),
        MessageRepository(connection),
        AgentProfileRepository(connection),
        NodeRepository(connection),
        BindRepository(connection),
    )


def test_user_and_conversation_roundtrip(tmp_path: Path) -> None:
    """Persist users and conversations and read them back with participants."""
    users, conversations, _, _, _, _ = _build_repositories(tmp_path)

    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")

    created = conversations.create_conversation(
        title="Alice & Bob", participant_ids=[alice.id, bob.id]
    )

    items = conversations.list_conversations()

    assert len(items) == 1
    assert items[0].id == created.id
    assert set(items[0].participant_ids) == {alice.id, bob.id}


def test_message_roundtrip_keeps_order(tmp_path: Path) -> None:
    """Persist messages and return them in creation order within a conversation."""
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="聊天", participant_ids=[alice.id]
    )

    first = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello",
    )
    second = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="world",
    )

    listed = messages.list_messages(conversation_id=conversation.id)

    assert [item.id for item in listed] == [first.id, second.id]
    assert [item.content for item in listed] == ["hello", "world"]
    assert listed[0].delivery_status == "completed"


def test_repositories_reject_invalid_relationships(tmp_path: Path) -> None:
    """Raise validation errors for invalid participant/message relationships."""
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")

    with pytest.raises(ValueError):
        conversations.create_conversation(title="空会话", participant_ids=[])

    conversation = conversations.create_conversation(title="聊天", participant_ids=[alice.id])

    with pytest.raises(ValueError):
        messages.create_message(
            conversation_id="missing-conversation",
            sender_user_id=alice.id,
            content="oops",
        )

    with pytest.raises(ValueError):
        messages.create_message(
            conversation_id=conversation.id,
            sender_user_id="missing-user",
            content="oops",
        )


def test_agent_profile_roundtrip_and_optimistic_lock(tmp_path: Path) -> None:
    """Persist profiles and reject stale profile_version updates."""
    users, conversations, _, profiles, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_user = users.create_user(username="agent-1", display_name="Alpha")
    seeded = profiles.upsert_profile(
        agent_id=agent_user.id,
        owner_id=owner.owner_id,
        display_name="Alpha",
        description="initial",
        system_prompt="You are Alpha.",
        skills=["plan"],
        tool_allowlist=["read"],
        group_reply_policy="manual",
        default_model=None,
    )

    created_conversation = conversations.create_conversation(
        title="alpha thread",
        participant_ids=[owner.id, seeded.agent_id],
    )
    assert created_conversation.config_profile_version == 1

    updated = profiles.update_profile(
        agent_id=agent_user.id,
        profile_version=1,
        display_name="Alpha v2",
        description="updated",
        system_prompt="You are Alpha v2.",
        skills=["plan", "review"],
        tool_allowlist=["read", "edit"],
        group_reply_policy="auto",
        default_model="claude-sonnet-4",
    )
    assert updated.profile_version == 2
    assert updated.group_reply_policy == "auto"

    with pytest.raises(AgentProfileVersionConflictError):
        profiles.update_profile(
            agent_id=agent_user.id,
            profile_version=1,
            display_name="stale",
            description="stale",
            system_prompt="stale",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
        )


def test_direct_conversation_with_agent_alias_freezes_prompt_snapshot(tmp_path: Path) -> None:
    """Freeze agent snapshot metadata when direct chats target an alias user like `agent:<id>`."""
    users, conversations, _, profiles, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_alias = users.create_user(username="agent:agent-1", display_name="Alpha Alias")
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
    )

    created = conversations.create_conversation(
        title="alias direct",
        participant_ids=[owner.id, agent_alias.id],
    )
    stored = conversations.get_conversation(conversation_id=created.id)
    snapshot_row = conversations._connection.execute(
        "SELECT config_agent_id, config_profile_version, config_system_prompt FROM conversations WHERE id = ?",
        (created.id,),
    ).fetchone()

    assert created.type == "direct"
    assert created.config_profile_version == 1
    assert stored is not None
    assert stored.config_profile_version == 1
    assert snapshot_row is not None
    assert snapshot_row["config_agent_id"] == "agent-1"
    assert snapshot_row["config_profile_version"] == 1
    assert snapshot_row["config_system_prompt"] == "You are Alpha."


def test_user_nodes_and_bind_roundtrip(tmp_path: Path) -> None:
    """Track owned nodes and bind confirmation state in repositories."""
    users, _, _, profiles, nodes, binds = _build_repositories(tmp_path)
    owner = users.create_user(username="alice", display_name="Alice")
    nodes.upsert_node(node_id="node-1", node_name="MacBook")
    profiles.upsert_profile(
        agent_id="agent-1",
        owner_id="",
        display_name="Alpha",
        description="local",
        system_prompt="You are Alpha.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
    )
    profiles._connection.execute(
        "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
        ("node-1", "agent-1"),
    )
    profiles._connection.commit()

    bind = binds.create_bind_request(node_id="node-1", bind_base_url="http://127.0.0.1:8011/bind/confirm")
    assert bind.status == "pending"
    assert bind.bind_url.startswith("http://127.0.0.1:8011/bind/confirm?token=")

    confirmed = binds.confirm_bind_request(bind_token=bind.bind_token, user_id=owner.id)
    nodes.assign_owner(node_id="node-1", owner_id=owner.owner_id)
    profiles.reassign_owner_by_node(node_id="node-1", owner_id=owner.owner_id)

    user = users.get_user(user_id=owner.id)
    assert user is not None
    assert user.owned_node_ids == ["node-1"]
    assert confirmed.status == "confirmed"
    assert profiles.get_profile(agent_id="agent-1").owner_id == owner.owner_id
