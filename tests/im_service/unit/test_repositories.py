"""Unit tests for IM repositories backed by SQLite."""

from pathlib import Path

import pytest

from IM.infra.db import connect, initialize_schema
from IM.repositories import (
    AgentProfileRepository,
    AgentProfileVersionConflictError,
    BindRepository,
    ConversationRepository,
    EventRepository,
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
        workspace_root=None,
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
        workspace_root="/srv/agents/alpha",
    )
    assert updated.profile_version == 2
    assert updated.group_reply_policy == "auto"
    assert updated.workspace_root == "/srv/agents/alpha"

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
            workspace_root=None,
        )


def test_initialize_schema_backfills_missing_agent_workspace_roots(tmp_path: Path) -> None:
    """Backfill legacy profiles that still have a NULL managed workspace root."""
    db_path = tmp_path / "im.db"
    connection = connect(db_path)
    initialize_schema(connection)
    connection.execute(
        """
        INSERT INTO agent_profiles(
            agent_id,
            owner_id,
            node_id,
            display_name,
            description,
            system_prompt,
            skills_json,
            tool_allowlist_json,
            group_reply_policy,
            default_model,
            workspace_root,
            profile_version,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "agent-legacy",
            "",
            None,
            "Legacy",
            "legacy row",
            "You are Legacy.",
            "[]",
            "[]",
            "manual",
            None,
            None,
            1,
            "2026-03-17T00:00:00Z",
            "2026-03-17T00:00:00Z",
        ),
    )
    connection.commit()

    initialize_schema(connection)

    row = connection.execute(
        "SELECT workspace_root FROM agent_profiles WHERE agent_id = ?",
        ("agent-legacy",),
    ).fetchone()
    assert row is not None
    assert row["workspace_root"].endswith("/nano-assistant/workspace/agent-legacy")



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
        workspace_root=None,
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


def test_create_message_accepts_agent_actor_sender_id(tmp_path: Path) -> None:
    """Accept agent sender ids and expose sender(actor) in returned message model."""
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_alias = users.create_user(username="agent:A", display_name="A")
    conversation = conversations.create_conversation(
        title="agent direct",
        participant_ids=[owner.id, agent_alias.id],
    )

    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id="agent:A",
        sender_type="agent",
        content="ack",
    )
    listed = messages.list_messages(conversation_id=conversation.id)
    stored = conversations.get_conversation(conversation_id=conversation.id)

    assert created.sender_user_id == agent_alias.id
    assert created.sender is not None
    assert created.sender.type == "agent"
    assert created.sender.id == "A"
    assert len(listed) == 1
    assert listed[0].sender is not None
    assert listed[0].sender.type == "agent"
    assert listed[0].sender.id == "A"
    assert stored is not None
    assert stored.last_message_preview == "ack"
    assert stored.last_message_at is not None


def test_initialize_schema_backfills_last_message_preview_from_latest_message(tmp_path: Path) -> None:
    """Backfill last_message_preview so inbox list data survives restarts without N message fetches."""
    db_path = tmp_path / "im.db"
    connection = connect(db_path)
    initialize_schema(connection)
    connection.execute(
        """
        INSERT INTO users(id, username, display_name, owner_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("user-1", "alice", "Alice", "owner-1", "2026-03-26T00:00:00Z"),
    )
    connection.execute(
        """
        INSERT INTO conversations(
            id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("conv-1", "Alpha", "direct", "owner-1", "user-1", 0, 0, 1, "2026-03-26T00:02:00Z", "2026-03-26T00:00:00Z"),
    )
    connection.execute(
        """
        INSERT INTO conversation_participants(conversation_id, user_id)
        VALUES (?, ?)
        """,
        ("conv-1", "user-1"),
    )
    connection.execute(
        """
        INSERT INTO messages(
            id, conversation_id, sender_user_id, sender_type, content, attachments_json, delivery_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("msg-1", "conv-1", "user-1", "user", "latest preview", "[]", "completed", "2026-03-26T00:02:00Z"),
    )
    connection.commit()

    connection.execute("ALTER TABLE conversations DROP COLUMN last_message_preview")
    connection.commit()

    initialize_schema(connection)

    row = connection.execute(
        "SELECT last_message_preview FROM conversations WHERE id = ?",
        ("conv-1",),
    ).fetchone()
    assert row is not None
    assert row["last_message_preview"] == "latest preview"


def test_event_repository_updates_last_message_preview_for_visible_relay_events(tmp_path: Path) -> None:
    """Persist relay-visible events into conversation summaries so inbox preview matches reopened threads."""
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    events = EventRepository(messages._connection)
    owner = users.create_user(username="owner", display_name="Owner")
    conversation = conversations.create_conversation(title="relay thread", participant_ids=[owner.id])
    base_message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        content="question",
        auto_complete_delivery=False,
    )

    events.append_event(
        conversation_id=conversation.id,
        message_id=base_message.id,
        event_type="relay.completed",
        delivery_status="completed",
        payload={
            "message_id": base_message.id,
            "relay_task_id": "relay-1",
            "agent_id": "agent-a",
            "detail": "A\n\nGot it. What would you like to do?",
        },
    )

    stored = conversations.get_conversation(conversation_id=conversation.id)
    assert stored is not None
    assert stored.last_message_preview == "A\n\nGot it. What would you like to do?"
    assert stored.last_message_at is not None


def test_list_messages_merges_visible_relay_history_into_old_conversations(tmp_path: Path) -> None:
    """Return the same visible relay replies on first history load, even when only events were persisted."""
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    events = EventRepository(messages._connection)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_a = users.create_user(username="agent:A", display_name="A")
    agent_q = users.create_user(username="agent:Q", display_name="Q")
    conversation = conversations.create_conversation(
        title="A + Q",
        participant_ids=[owner.id, agent_a.id, agent_q.id],
    )
    prompt = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        content="大家下午去哪里了",
        auto_complete_delivery=False,
    )
    messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        content="@agent:A 你",
        auto_complete_delivery=False,
    )
    followup = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        content="@agent:Q 还有你",
        auto_complete_delivery=False,
    )
    relay_a_1 = events.append_event(
        conversation_id=conversation.id,
        message_id=prompt.id,
        event_type="relay.completed",
        delivery_status="completed",
        payload={
            "message_id": prompt.id,
            "relay_task_id": "relay-a-1",
            "agent_id": "A",
            "detail": "我不在现场，无法得知。你想让我帮你发消息问大家吗？",
        },
    )
    relay_q_1 = events.append_event(
        conversation_id=conversation.id,
        message_id=prompt.id,
        event_type="relay.completed",
        delivery_status="completed",
        payload={
            "message_id": prompt.id,
            "relay_task_id": "relay-q-1",
            "agent_id": "Q",
            "detail": "抱歉没明白，你是要我帮你问大家下午去哪儿了吗？",
        },
    )
    relay_a_2 = events.append_event(
        conversation_id=conversation.id,
        message_id=followup.id,
        event_type="relay.completed",
        delivery_status="completed",
        payload={
            "message_id": followup.id,
            "relay_task_id": "relay-a-2",
            "agent_id": "A",
            "detail": "我在这儿呢。你是指今天下午大家都去哪儿了吗？我这边没收到行程消息，要不要我帮你问一下？",
        },
    )
    relay_q_2 = events.append_event(
        conversation_id=conversation.id,
        message_id=followup.id,
        event_type="relay.completed",
        delivery_status="completed",
        payload={
            "message_id": followup.id,
            "relay_task_id": "relay-q-2",
            "agent_id": "Q",
            "detail": "在的。你想让我做什么？",
        },
    )
    messages._connection.execute(
        "UPDATE messages SET created_at = ? WHERE id = ?",
        ("2026-03-26T00:00:00Z", prompt.id),
    )
    messages._connection.execute(
        "UPDATE messages SET created_at = ? WHERE content = ?",
        ("2026-03-26T00:00:03Z", "@agent:A 你"),
    )
    messages._connection.execute(
        "UPDATE messages SET created_at = ? WHERE id = ?",
        ("2026-03-26T00:00:04Z", followup.id),
    )
    messages._connection.execute(
        "UPDATE conversation_events SET created_at = ? WHERE event_id = ?",
        ("2026-03-26T00:00:01Z", relay_a_1.event_id),
    )
    messages._connection.execute(
        "UPDATE conversation_events SET created_at = ? WHERE event_id = ?",
        ("2026-03-26T00:00:02Z", relay_q_1.event_id),
    )
    messages._connection.execute(
        "UPDATE conversation_events SET created_at = ? WHERE event_id = ?",
        ("2026-03-26T00:00:05Z", relay_a_2.event_id),
    )
    messages._connection.execute(
        "UPDATE conversation_events SET created_at = ? WHERE event_id = ?",
        ("2026-03-26T00:00:06Z", relay_q_2.event_id),
    )
    messages._connection.commit()

    listed = messages.list_messages(conversation_id=conversation.id)

    assert [item.content for item in listed] == [
        "大家下午去哪里了",
        "我不在现场，无法得知。你想让我帮你发消息问大家吗？",
        "抱歉没明白，你是要我帮你问大家下午去哪儿了吗？",
        "@agent:A 你",
        "@agent:Q 还有你",
        "我在这儿呢。你是指今天下午大家都去哪儿了吗？我这边没收到行程消息，要不要我帮你问一下？",
        "在的。你想让我做什么？",
    ]
    assert [item.id for item in listed if item.sender_type == "agent"] == [
        f"{prompt.id}:relay:relay-a-1",
        f"{prompt.id}:relay:relay-q-1",
        f"{followup.id}:relay:relay-a-2",
        f"{followup.id}:relay:relay-q-2",
    ]
    assert [item.sender.id for item in listed if item.sender_type == "agent"] == ["A", "Q", "A", "Q"]


def test_initialize_schema_reconciles_old_relay_preview_mismatches(tmp_path: Path) -> None:
    """Recompute stale conversation previews from the latest visible relay event on startup."""
    db_path = tmp_path / "im.db"
    connection = connect(db_path)
    initialize_schema(connection)
    connection.execute(
        """
        INSERT INTO users(id, username, display_name, owner_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("user-1", "alice", "Alice", "owner-1", "2026-03-26T00:00:00Z"),
    )
    connection.execute(
        """
        INSERT INTO conversations(
            id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_preview, last_message_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("conv-1", "Alpha", "direct", "owner-1", "user-1", 0, 0, 1, "11", "2026-03-26T00:01:00Z", "2026-03-26T00:00:00Z"),
    )
    connection.execute(
        """
        INSERT INTO conversation_participants(conversation_id, user_id)
        VALUES (?, ?)
        """,
        ("conv-1", "user-1"),
    )
    connection.execute(
        """
        INSERT INTO messages(
            id, conversation_id, sender_user_id, sender_type, content, attachments_json, delivery_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("msg-1", "conv-1", "user-1", "user", "11", "[]", "completed", "2026-03-26T00:01:00Z"),
    )
    connection.execute(
        """
        INSERT INTO conversation_events(
            conversation_id, message_id, event_type, delivery_status, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "conv-1",
            "msg-1",
            "relay.completed",
            "completed",
            '{"message_id":"msg-1","relay_task_id":"relay-1","detail":"A\\n\\nGot it. What would you like to do?"}',
            "2026-03-26T00:02:00Z",
        ),
    )
    connection.commit()

    initialize_schema(connection)

    row = connection.execute(
        "SELECT last_message_preview, last_message_at FROM conversations WHERE id = ?",
        ("conv-1",),
    ).fetchone()
    assert row is not None
    assert row["last_message_preview"] == "A\n\nGot it. What would you like to do?"
    assert row["last_message_at"] == "2026-03-26T00:02:00Z"


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
