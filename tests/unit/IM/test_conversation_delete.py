"""Persistence tests for creator-authorized conversation deletion."""

from pathlib import Path

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.users import UserRepository


def _build_repos(tmp_path: Path) -> tuple[UserRepository, ConversationRepository]:
    """Build repositories bound to a temporary SQLite database."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return UserRepository(connection), ConversationRepository(connection)


# ---------------------------------------------------------------------------
# delete_conversation
# ---------------------------------------------------------------------------


def test_delete_conversation_by_creator_cascades_data(tmp_path: Path) -> None:
    """Creator can delete a group conversation; messages and participants cascade."""
    users, conversations = _build_repos(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    carol = users.create_user(username="carol", display_name="Carol")

    convo = conversations.create_conversation(
        title="Team chat",
        participant_ids=[alice.id, bob.id, carol.id],
        creator_id=alice.id,
    )

    # Deletion by creator must not raise.
    conversations.delete_conversation(conversation_id=convo.id, requester_id=alice.id)

    # Conversation is gone.
    assert conversations.get_conversation(conversation_id=convo.id) is None
    assert conversations.list_conversations() == []


def test_delete_conversation_by_non_creator_raises_permission_error(
    tmp_path: Path,
) -> None:
    """Non-creator cannot delete a conversation; raises PermissionError."""
    users, conversations = _build_repos(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")

    convo = conversations.create_conversation(
        title="Team chat",
        participant_ids=[alice.id, bob.id],
        creator_id=alice.id,
    )

    with pytest.raises(PermissionError):
        conversations.delete_conversation(conversation_id=convo.id, requester_id=bob.id)

    # Conversation must still exist.
    assert conversations.get_conversation(conversation_id=convo.id) is not None


def test_delete_conversation_not_found_raises(tmp_path: Path) -> None:
    """Raise ValueError when conversation does not exist."""
    _, conversations = _build_repos(tmp_path)

    with pytest.raises(ValueError, match="conversation_id not found"):
        conversations.delete_conversation(
            conversation_id="nonexistent", requester_id="any"
        )
