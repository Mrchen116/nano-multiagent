"""Unit tests for message repository: roundtrip, relay history, dedup logic."""

from pathlib import Path

from IM.infra.db import connect, initialize_schema
from IM.repositories import (
    AgentProfileRepository,
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


def test_list_messages_drops_relay_mirror_when_real_agent_message_exists(tmp_path: Path) -> None:
    """When a turn produced both a real agent message and a relay.completed mirror, the mirror is suppressed."""
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    events = EventRepository(messages._connection)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_user = users.create_user(username="agent:alpha", display_name="Alpha")
    conversation = conversations.create_conversation(
        title="direct alpha",
        participant_ids=[owner.id, agent_user.id],
    )
    user_msg = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        content="Hello",
        auto_complete_delivery=False,
    )
    real_agent_msg = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=agent_user.id,
        sender_type="agent",
        content="Hi back",
        auto_complete_delivery=False,
    )
    events.append_event(
        conversation_id=conversation.id,
        message_id=user_msg.id,
        event_type="relay.completed",
        delivery_status="completed",
        payload={
            "message_id": user_msg.id,
            "relay_task_id": "relay-dup-1",
            "agent_id": "alpha",
            "detail": "Hi back",
        },
    )

    listed = messages.list_messages(conversation_id=conversation.id)
    listed_ids = [m.id for m in listed]
    # Expect: user msg + real agent msg, but no synthetic relay mirror id.
    assert user_msg.id in listed_ids
    assert real_agent_msg.id in listed_ids
    assert not any(":relay:" in mid for mid in listed_ids), (
        f"Expected relay mirror to be suppressed when real agent message exists; got {listed_ids}"
    )


def test_list_messages_keeps_relay_mirror_when_no_real_agent_message(tmp_path: Path) -> None:
    """Old conversations without real agent messages still surface relay.completed mirror rows."""
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    events = EventRepository(messages._connection)
    owner = users.create_user(username="owner", display_name="Owner")
    conversation = conversations.create_conversation(
        title="legacy",
        participant_ids=[owner.id],
    )
    user_msg = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        content="hi",
        auto_complete_delivery=False,
    )
    events.append_event(
        conversation_id=conversation.id,
        message_id=user_msg.id,
        event_type="relay.completed",
        delivery_status="completed",
        payload={
            "message_id": user_msg.id,
            "relay_task_id": "relay-legacy-1",
            "agent_id": "legacy",
            "detail": "legacy answer",
        },
    )

    listed = messages.list_messages(conversation_id=conversation.id)
    listed_ids = [m.id for m in listed]
    assert any(":relay:" in mid for mid in listed_ids), (
        f"Expected relay synthetic preserved when no real agent message; got {listed_ids}"
    )


def test_list_messages_dedups_relay_failed_when_real_terminal_row_exists(tmp_path: Path) -> None:
    """bugfix-365: a `relay.failed` event must not produce a second bubble when the
    real `messages` row with same `message_id` is already in `failed` terminal state.

    Pre-fix observed in production: watchdog wrote `relay.failed` after flipping the
    real message row to `failed`, and `_message_from_visible_event_row` rendered a
    second synthetic bubble (with anonymous `Agent` sender because payload lacked
    agent_id). Frontend showed two failed bubbles for one logical message.
    """
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    events = EventRepository(messages._connection)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_user = users.create_user(username="agent:archA", display_name="Q")
    conversation = conversations.create_conversation(
        title="g",
        participant_ids=[owner.id, agent_user.id],
    )
    user_msg = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        content="hi",
        auto_complete_delivery=False,
    )
    real_agent_msg = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=agent_user.id,
        sender_type="agent",
        content="",
        allow_empty=True,
        auto_complete_delivery=False,
    )
    events.update_message_delivery_status(
        message_id=real_agent_msg.id,
        delivery_status="failed",
    )
    events.append_event(
        conversation_id=conversation.id,
        message_id=real_agent_msg.id,
        event_type="relay.failed",
        delivery_status="failed",
        payload={
            "conversation_id": conversation.id,
            "message_id": real_agent_msg.id,
            "progress_state": "failed",
            "semantic": "relay_watchdog_timeout",
            "detail": "relay timed out after 300s with no completion event",
            "reason": "watchdog_timeout",
        },
    )

    listed = messages.list_messages(conversation_id=conversation.id)
    failed_rows = [m for m in listed if m.delivery_status == "failed"]
    assert len(failed_rows) == 1, (
        f"Expected exactly one failed bubble; got {[(m.id, m.sender_type) for m in failed_rows]}"
    )
    assert failed_rows[0].id == real_agent_msg.id, "The kept failed bubble must be the real message row, not a synthetic"
