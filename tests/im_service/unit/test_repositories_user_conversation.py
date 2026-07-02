"""Unit tests for user, conversation, node, and bind repositories."""

from pathlib import Path
import json

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    AgentProfileRepository,
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
    assert [item.type for item in items[0].participants] == ["user", "user"]


def test_repositories_reject_invalid_relationships(tmp_path: Path) -> None:
    """Raise validation errors for invalid participant/message relationships."""
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")

    with pytest.raises(ValueError):
        conversations.create_conversation(title="空会话", participant_ids=[])

    conversation = conversations.create_conversation(
        title="聊天", participant_ids=[alice.id]
    )

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


def test_create_conversation_accepts_actor_references(tmp_path: Path) -> None:
    """Accept actor-style participant references (`user:`/`agent:`) at repository boundary."""
    users, conversations, _, _, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_alias = users.create_user(username="agent:agent-q", display_name="Q")

    created = conversations.create_conversation(
        title="actor refs",
        participant_ids=[f"user:{owner.id}", "agent:agent-q"],
    )
    stored = conversations.get_conversation(conversation_id=created.id)

    assert stored is not None
    assert stored.type == "direct"
    assert stored.direct_kind == "user-agent"
    assert [item.type for item in stored.participants] == ["user", "agent"]
    assert [item.id for item in stored.participants] == [owner.id, "agent-q"]


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
        workspace_root=None,
    )
    profiles._connection.execute(
        "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
        ("node-1", "agent-1"),
    )
    profiles._connection.commit()

    bind = binds.create_bind_request(
        node_id="node-1", bind_base_url="http://127.0.0.1:8011/bind/confirm"
    )
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


def test_create_group_conversation_owner_id_uses_caller(tmp_path: Path) -> None:
    """create_conversation must use caller_owner_id when participants span multiple owners.

    Regression for R3-1: multi-owner participants previously generated a random UUID
    as the conversation owner_id, making list_conversations_for_owner unable to find it.
    """
    users, conversations, _, _, _, _ = _build_repositories(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    # Agent user with empty owner_id simulates an unbound/ownerless agent participant
    agent_user = users.create_user(username="agent:bot", display_name="Bot")
    # Ensure agent has no owner (owner_id='')
    conversations._connection.execute(
        "UPDATE users SET owner_id = '' WHERE id = ?", (agent_user.id,)
    )
    conversations._connection.commit()

    created = conversations.create_conversation(
        title="Alice + Bot group",
        participant_ids=[alice.id, agent_user.id],
        caller_owner_id=alice.owner_id,
    )

    assert created.owner_id == alice.owner_id, (
        f"Expected owner_id={alice.owner_id!r}, got {created.owner_id!r}; "
        "multi-owner participants must use caller_owner_id, not a random UUID"
    )
    visible = conversations.list_conversations_for_owner(owner_id=alice.owner_id)
    assert any(c.id == created.id for c in visible), (
        "Newly created group conversation must appear in caller's conversation list"
    )


def test_conversation_exposes_run_state_and_source_jsonl_path(
    tmp_path: Path,
) -> None:
    """Conversation rows expose distill-safe runtime metadata from existing sources."""
    users, conversations, _, profiles, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="alice", display_name="Alice")
    agent_user = users.create_user(username="agent:agent-1", display_name="Agent 1")
    workspace_root = tmp_path / "agent-1-workspace"
    profiles.upsert_profile(
        agent_id="agent-1",
        owner_id=owner.owner_id,
        display_name="Agent 1",
        description="",
        system_prompt="You are Agent 1.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=str(workspace_root),
    )

    created = conversations.create_conversation(
        title="Alice & Agent",
        participant_ids=[owner.id, agent_user.id],
        caller_owner_id=owner.owner_id,
    )
    session_path = workspace_root / ".nanoassistant" / "sessions" / "sess-1.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(
        json.dumps(
            {
                "type": "session_created",
                "session_id": "sess-1",
                "created_at": "2026-01-01T00:00:00Z",
                "workspace_root": str(workspace_root),
                "metadata": {
                    "agent_id": "agent-1",
                    "conversation_id": created.id,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    listed = conversations.list_conversations_for_owner(owner_id=owner.owner_id)

    assert listed[0].id == created.id
    assert listed[0].run_state == "idle"
    assert listed[0].source_agent_id == "agent-1"
    assert listed[0].source_jsonl_path == str(session_path)


def test_conversation_run_state_is_running_for_active_agent_message(
    tmp_path: Path,
) -> None:
    """A non-terminal agent bubble makes the conversation unavailable for distill."""
    users, conversations, messages, profiles, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="alice", display_name="Alice")
    agent_user = users.create_user(username="agent:agent-1", display_name="Agent 1")
    profiles.upsert_profile(
        agent_id="agent-1",
        owner_id=owner.owner_id,
        display_name="Agent 1",
        description="",
        system_prompt="You are Agent 1.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=str(tmp_path / "agent-1-workspace"),
    )
    created = conversations.create_conversation(
        title="Alice & Agent",
        participant_ids=[owner.id, agent_user.id],
        caller_owner_id=owner.owner_id,
    )
    messages.create_message(
        conversation_id=created.id,
        sender_user_id=agent_user.id,
        sender_type="agent",
        content="",
        allow_empty=True,
        auto_complete_delivery=False,
        delivery_status="running",
    )

    listed = conversations.list_conversations_for_owner(owner_id=owner.owner_id)

    assert listed[0].run_state == "running"
