"""Unit tests for conversation event persistence behavior."""

from pathlib import Path

from IM.infra.db import connect, initialize_schema
from IM.repositories import ConversationRepository, EventRepository, MessageRepository, UserRepository


def _build_repositories(
    tmp_path: Path,
) -> tuple[UserRepository, ConversationRepository, MessageRepository, EventRepository]:
    """Build repositories sharing one temporary SQLite database."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return (
        UserRepository(connection),
        ConversationRepository(connection),
        MessageRepository(connection),
        EventRepository(connection),
    )


def test_create_message_persists_delivery_events_in_order(tmp_path: Path) -> None:
    """Write sent/completed events when creating a conversation message."""
    users, conversations, messages, events = _build_repositories(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(title="chat", participant_ids=[alice.id])

    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello",
    )

    listed_events = events.list_events(conversation_id=conversation.id)

    assert created.delivery_status == "completed"
    assert [item.event_type for item in listed_events] == ["message.sent", "message.delivered"]
    assert [item.delivery_status for item in listed_events] == ["sent", "completed"]
    assert [item.message_id for item in listed_events] == [created.id, created.id]
    assert listed_events[0].event_id < listed_events[1].event_id


def test_create_message_can_defer_delivery_until_gateway_receipt(tmp_path: Path) -> None:
    """Allow relay paths to persist only message.sent before gateway completion."""
    users, conversations, messages, events = _build_repositories(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(title="chat", participant_ids=[alice.id])

    created = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello",
        auto_complete_delivery=False,
    )

    listed_events = events.list_events(conversation_id=conversation.id)

    assert created.delivery_status == "sent"
    assert [item.event_type for item in listed_events] == ["message.sent"]
    assert [item.delivery_status for item in listed_events] == ["sent"]
    assert listed_events[0].message_id == created.id


def test_list_events_supports_after_event_id_cursor(tmp_path: Path) -> None:
    """Read only events newer than a given event id cursor."""
    users, conversations, messages, events = _build_repositories(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(title="chat", participant_ids=[alice.id])

    messages.create_message(conversation_id=conversation.id, sender_user_id=alice.id, content="m1")
    messages.create_message(conversation_id=conversation.id, sender_user_id=alice.id, content="m2")

    all_events = events.list_events(conversation_id=conversation.id)
    cursor = all_events[1].event_id

    incremental = events.list_events(conversation_id=conversation.id, after_event_id=cursor)

    assert len(incremental) == len(all_events) - 2
    assert all(item.event_id > cursor for item in incremental)


def test_get_latest_event_id_returns_zero_for_empty_conversation(tmp_path: Path) -> None:
    """Return zero when a conversation has no persisted events yet."""
    users, conversations, _messages, events = _build_repositories(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(title="chat", participant_ids=[alice.id])

    assert events.get_latest_event_id(conversation_id=conversation.id) == 0


def test_get_latest_event_id_returns_max_persisted_event_id(tmp_path: Path) -> None:
    """Expose the highest stored event id for one conversation."""
    users, conversations, messages, events = _build_repositories(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(title="chat", participant_ids=[alice.id])

    messages.create_message(conversation_id=conversation.id, sender_user_id=alice.id, content="m1")
    messages.create_message(conversation_id=conversation.id, sender_user_id=alice.id, content="m2")

    all_events = events.list_events(conversation_id=conversation.id)

    assert events.get_latest_event_id(conversation_id=conversation.id) == all_events[-1].event_id
