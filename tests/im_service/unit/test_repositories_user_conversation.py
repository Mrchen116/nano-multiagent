"""Unit tests for user, conversation, node, and bind repositories."""

from pathlib import Path
import sqlite3

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.bindings import BindRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.nodes import NodeRepository
from IM.infra.repositories.users import UserRepository


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


def test_conversation_exposes_run_state_and_source_node(
    tmp_path: Path,
) -> None:
    """Conversation rows project their source Gateway without opening a workspace."""
    users, conversations, _, profiles, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="alice", display_name="Alice")
    agent_user = users.create_user(username="agent:agent-1", display_name="Agent 1")
    profiles.upsert_profile(
        agent_id="agent-1",
        owner_id=owner.owner_id,
        display_name="Agent 1",
        description="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root="/not-accessed-by-im",
        node_id="node-1",
    )

    created = conversations.create_conversation(
        title="Alice & Agent",
        participant_ids=[owner.id, agent_user.id],
        caller_owner_id=owner.owner_id,
    )
    listed = conversations.list_conversations_for_owner(owner_id=owner.owner_id)

    assert listed[0].id == created.id
    assert listed[0].run_state == "idle"
    assert listed[0].source_agent_id == "agent-1"
    assert listed[0].source_node_id == "node-1"


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


def test_external_conversation_find_or_create_is_agent_scoped_and_updates_title(
    tmp_path: Path,
) -> None:
    """Find or create one shadow conversation per external chat, owner, and agent."""
    users, conversations, _, profiles, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    users.create_user(username="agent:plato", display_name="Plato")
    users.create_user(username="agent:luban", display_name="Luban")
    profiles.upsert_profile(
        agent_id="plato",
        owner_id=owner.owner_id,
        display_name="Plato",
        description="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=None,
    )
    profiles.upsert_profile(
        agent_id="luban",
        owner_id=owner.owner_id,
        display_name="Luban",
        description="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=None,
    )

    first = conversations.find_or_create_external_conversation(
        external_source="feishu",
        external_chat_id="oc_product",
        agent_id="plato",
        title="Plato · 产品群 · feishu",
        is_group=True,
        participant_ids=[f"user:{owner.id}", "agent:plato"],
        owner_id=owner.owner_id,
        creator_id=f"user:{owner.id}",
    )
    second = conversations.find_or_create_external_conversation(
        external_source="feishu",
        external_chat_id="oc_product",
        agent_id="plato",
        title="Plato · Renamed · feishu",
        is_group=True,
        participant_ids=[f"user:{owner.id}", "agent:plato"],
        owner_id=owner.owner_id,
        creator_id=f"user:{owner.id}",
    )
    other_agent = conversations.find_or_create_external_conversation(
        external_source="feishu",
        external_chat_id="oc_product",
        agent_id="luban",
        title="Luban · 产品群 · feishu",
        is_group=True,
        participant_ids=[f"user:{owner.id}", "agent:luban"],
        owner_id=owner.owner_id,
        creator_id=f"user:{owner.id}",
    )

    assert second.conversation.id == first.conversation.id
    assert second.conversation.title == "Plato · Renamed · feishu"
    assert second.conversation.type == "group"
    assert second.conversation.config_agent_id == "plato"
    assert second.conversation.external_source == "feishu"
    assert second.conversation.external_chat_id == "oc_product"
    assert other_agent.conversation.id != first.conversation.id
    assert other_agent.conversation.config_agent_id == "luban"

    with pytest.raises(sqlite3.IntegrityError):
        conversations._connection.execute(  # noqa: SLF001
            """
            INSERT INTO conversations(
                id, title, type, owner_id, creator_id, config_agent_id,
                external_source, external_chat_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "duplicate-shadow",
                "Duplicate",
                "group",
                owner.owner_id,
                owner.id,
                "plato",
                "feishu",
                "oc_product",
                "2026-01-01T00:00:00Z",
            ),
        )
