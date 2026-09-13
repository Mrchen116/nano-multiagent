"""Personal conversation state and ordinary direct identity persistence."""

from pathlib import Path
from tests.im_service.unit.test_repositories_user_conversation import (
    _build_repositories,
)


def test_members_have_independent_preferences_and_read_boundaries(
    tmp_path: Path,
) -> None:
    """Membership, not ownership, grants a personal view without consuming later messages."""
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    alice = users.create_user(
        username="reader-a", display_name="A", password_hash="hash"
    )
    bob = users.create_user(username="reader-b", display_name="B", password_hash="hash")
    outsider = users.create_user(
        username="reader-c", display_name="C", password_hash="hash"
    )
    chat = conversations.create_conversation(
        title="Group",
        participant_ids=[alice.id, bob.id],
        conversation_type="group",
        caller_owner_id=alice.id,
    )
    conversations.update_conversation(
        conversation_id=chat.id,
        user_id=bob.id,
        title=None,
        is_pinned=True,
        is_muted=True,
    )
    first = messages.create_message(
        conversation_id=chat.id, sender_user_id=alice.id, content="first"
    )
    second = messages.create_message(
        conversation_id=chat.id,
        sender_user_id=alice.id,
        content="second",
        caller_idempotency_key="second",
    )
    messages.create_message(
        conversation_id=chat.id,
        sender_user_id=alice.id,
        content="second",
        caller_idempotency_key="second",
    )
    messages.list_messages(conversation_id=chat.id)
    b = conversations.get_conversation_for_member(
        conversation_id=chat.id, user_id=bob.id
    )
    a = conversations.get_conversation_for_member(
        conversation_id=chat.id, user_id=alice.id
    )
    assert (b.is_pinned, b.is_muted, b.unread_count) == (True, True, 2)
    assert (a.is_pinned, a.is_muted, a.unread_count) == (False, False, 0)
    assert (
        conversations.mark_read(
            conversation_id=chat.id, user_id=bob.id, last_read_message_id=first.id
        ).unread_count
        == 1
    )
    assert (
        conversations.mark_read(
            conversation_id=chat.id, user_id=bob.id, last_read_message_id=second.id
        ).unread_count
        == 0
    )
    assert (
        conversations.mark_read(
            conversation_id=chat.id, user_id=bob.id, last_read_message_id=first.id
        ).unread_count
        == 0
    )
    conversations.add_participants(conversation_id=chat.id, references=[outsider.id])
    assert (
        conversations.get_conversation_for_member(
            conversation_id=chat.id, user_id=outsider.id
        ).unread_count
        == 0
    )


def test_normal_direct_reuses_pair_but_branches_and_groups_are_independent(
    tmp_path: Path,
) -> None:
    """Explicit groups and special execution chats never consume a normal direct key."""
    users, conversations, _, _, _, _ = _build_repositories(tmp_path)
    alice = users.create_user(username="pair-a", display_name="A")
    bob = users.create_user(username="pair-b", display_name="B")

    def create(kind, participants, reuse=False):
        return conversations.create_conversation(
            title="Chat",
            participant_ids=participants,
            conversation_type=kind,
            reuse_direct=reuse,
        )

    first = create("direct", [alice.id, bob.id], True)
    assert create("direct", [bob.id, alice.id], True).id == first.id
    assert create("direct", [alice.id, bob.id]).id != first.id
    assert create("group", [alice.id, bob.id]).type == "group"


def test_discarded_placeholder_only_decrements_members_who_had_not_read_it(
    tmp_path: Path,
) -> None:
    """A rollback cannot consume a later message or someone else's read state."""
    users, conversations, messages, _, _, _ = _build_repositories(tmp_path)
    alice = users.create_user(username="a", display_name="A", password_hash="hash")
    bob = users.create_user(username="b", display_name="B", password_hash="hash")
    agent = users.create_user(username="agent:worker", display_name="Worker")
    chat = conversations.create_conversation(
        title="Team", participant_ids=[alice.id, bob.id, agent.id]
    )
    placeholder = messages.create_message(
        conversation_id=chat.id,
        sender_user_id=agent.id,
        sender_type="agent",
        content="",
        allow_empty=True,
        delivery_status="running",
        auto_complete_delivery=False,
    )
    messages.update_runtime_state(message_id=placeholder.id, delivery_status="running")
    conversations.mark_read(
        conversation_id=chat.id, user_id=alice.id, last_read_message_id=placeholder.id
    )
    later = messages.create_message(
        conversation_id=chat.id, sender_user_id=bob.id, content="later"
    )
    messages.discard_running_agent_message(message_id=placeholder.id, reason="empty")
    assert (
        conversations.get_conversation_for_member(
            conversation_id=chat.id, user_id=alice.id
        ).unread_count
        == 1
    )
    assert (
        conversations.get_conversation_for_member(
            conversation_id=chat.id, user_id=bob.id
        ).unread_count
        == 0
    )
    assert (
        conversations.mark_read(
            conversation_id=chat.id, user_id=alice.id, last_read_message_id=later.id
        ).unread_count
        == 0
    )
