"""Unit tests for relay task lifecycle: enqueue idempotency, delivery receipt, and profile snapshot."""

from pathlib import Path

from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    AgentProfileRepository,
    ConversationRepository,
    MessageRepository,
    UserRepository,
)


def _build_fixture(
    tmp_path: Path,
) -> tuple[
    RelayService,
    MessageRepository,
    ConversationRepository,
    UserRepository,
    AgentProfileRepository,
]:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    relay_service = RelayService(connection)
    profiles = AgentProfileRepository(connection)
    return relay_service, messages, conversations, users, profiles


def test_enqueue_message_relay_is_idempotent(tmp_path: Path) -> None:
    """Reuse the same relay task when idempotency_key repeats."""
    relay_service, messages, conversations, users, _profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="chat", participant_ids=[alice.id]
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello",
    )

    first = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-1",
        sender_user_id=alice.id,
    )
    second = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-1",
        sender_user_id=alice.id,
    )

    assert first.created is True
    assert second.created is False
    assert first.relay_task.relay_task_id == second.relay_task.relay_task_id
    assert first.relay_task.payload["message"]["id"] == message.id


def test_apply_delivery_receipt_updates_task_status(tmp_path: Path) -> None:
    """Persist sent/completed receipt states on relay tasks."""
    relay_service, messages, conversations, users, _profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="chat", participant_ids=[alice.id]
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello",
    )
    created = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-2",
        sender_user_id=alice.id,
    )

    dispatched = relay_service.mark_dispatched(
        relay_task_id=created.relay_task.relay_task_id
    )
    sent = relay_service.apply_delivery_receipt(
        relay_task_id=created.relay_task.relay_task_id,
        delivery_status="sent",
        detail=None,
    )
    completed = relay_service.apply_delivery_receipt(
        relay_task_id=created.relay_task.relay_task_id,
        delivery_status="completed",
        detail="ok",
    )

    assert dispatched.status == "dispatched"
    assert sent.status == "sent"
    assert sent.receipt_status == "sent"
    assert completed.status == "completed"
    assert completed.receipt_status == "completed"
    assert completed.receipt_detail == "ok"


def test_direct_conversation_relay_keeps_old_snapshot_while_new_conversation_uses_updated_profile(
    tmp_path: Path,
) -> None:
    """Freeze old direct-chat relay metadata after profile edits while new direct chats use the latest config."""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_alias = users.create_user(
        username="agent:agent-a", display_name="Agent A Alias"
    )
    profiles.upsert_profile(
        agent_id="agent-a",
        owner_id=owner.owner_id,
        display_name="Agent A",
        description="profile a",
        system_prompt="You are agent-a.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    old_conversation = conversations.create_conversation(
        title="old direct",
        participant_ids=[owner.id, agent_alias.id],
    )

    profiles.update_profile(
        agent_id="agent-a",
        profile_version=1,
        display_name="Agent A v2",
        description="profile a v2",
        system_prompt="You are upgraded.",
        skills=["plan"],
        tool_allowlist=["read"],
        group_reply_policy="manual",
        default_model="claude-sonnet-4",
    )
    new_conversation = conversations.create_conversation(
        title="new direct",
        participant_ids=[owner.id, agent_alias.id],
    )

    old_message = messages.create_message(
        conversation_id=old_conversation.id,
        sender_user_id=owner.id,
        content="hello old",
    )
    new_message = messages.create_message(
        conversation_id=new_conversation.id,
        sender_user_id=owner.id,
        content="hello new",
    )

    old_created = relay_service.enqueue_message_relay(
        message=old_message,
        target_node_id="node-1",
        idempotency_key="idem-old-direct",
        sender_user_id=owner.id,
        conversation_type="direct",
    )
    new_created = relay_service.enqueue_message_relay(
        message=new_message,
        target_node_id="node-1",
        idempotency_key="idem-new-direct",
        sender_user_id=owner.id,
        conversation_type="direct",
    )

    assert old_created.relay_task.payload["agent_id"] == "agent-a"
    assert old_created.relay_task.payload["metadata"] == {
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 1,
    }
    assert new_created.relay_task.payload["agent_id"] == "agent-a"
    assert new_created.relay_task.payload["metadata"] == {
        "conversation_type": "direct",
        "mentioned_agent_ids": [],
        "config_profile_version": 2,
    }
