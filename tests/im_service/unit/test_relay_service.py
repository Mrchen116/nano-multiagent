"""Unit tests for IM relay task orchestration."""

from pathlib import Path

from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.repositories import AgentProfileRepository, ConversationRepository, MessageRepository, UserRepository


def _build_fixture(tmp_path: Path) -> tuple[RelayService, MessageRepository, ConversationRepository, UserRepository, AgentProfileRepository]:
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
    conversation = conversations.create_conversation(title="chat", participant_ids=[alice.id])
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
    conversation = conversations.create_conversation(title="chat", participant_ids=[alice.id])
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

    dispatched = relay_service.mark_dispatched(relay_task_id=created.relay_task.relay_task_id)
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


def test_enqueue_message_relay_targets_the_mentioned_agent_in_group_chats(tmp_path: Path) -> None:
    """Group relay payloads must snapshot the addressed agent instead of the first participant."""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    agent_a_user = users.create_user(username="agent:agent-a", display_name="Agent A")
    agent_b_user = users.create_user(username="agent:agent-b", display_name="Agent B")
    profiles.upsert_profile(
        agent_id="agent-a",
        owner_id=alice.owner_id,
        display_name="Agent A",
        description="profile a",
        system_prompt="You are agent-a.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
    )
    profiles.upsert_profile(
        agent_id="agent-b",
        owner_id=alice.owner_id,
        display_name="Agent B",
        description="profile b",
        system_prompt="You are agent-b.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
    )
    conversation = conversations.create_conversation(
        title="group",
        participant_ids=[alice.id, agent_a_user.id, agent_b_user.id],
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="@agent-b please reply in thread",
    )

    created = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-mentioned-agent",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    assert created.relay_task.payload["agent_id"] == "agent-b"
    assert created.relay_task.payload["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-b"],
        "config_profile_version": 1,
        "system_prompt": "You are agent-b.",
    }
