"""Unit tests for IM repositories backed by SQLite."""

from pathlib import Path

import pytest

from IM.infra.db import connect, initialize_schema
from IM.repositories import ConversationRepository, MessageRepository, UserRepository


def _build_repositories(tmp_path: Path) -> tuple[UserRepository, ConversationRepository, MessageRepository]:
    """Build repository instances bound to a temporary SQLite database."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return (
        UserRepository(connection),
        ConversationRepository(connection),
        MessageRepository(connection),
    )


def test_user_and_conversation_roundtrip(tmp_path: Path) -> None:
    """Persist users and conversations and read them back with participants."""
    users, conversations, _ = _build_repositories(tmp_path)

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
    users, conversations, messages = _build_repositories(tmp_path)
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


def test_repositories_reject_invalid_relationships(tmp_path: Path) -> None:
    """Raise validation errors for invalid participant/message relationships."""
    users, conversations, messages = _build_repositories(tmp_path)
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
