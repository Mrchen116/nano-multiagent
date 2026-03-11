"""Unit tests for IM relay task orchestration."""

from pathlib import Path

from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.repositories import ConversationRepository, MessageRepository, UserRepository


def _build_fixture(tmp_path: Path) -> tuple[RelayService, MessageRepository, str, str]:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    relay_service = RelayService(connection)

    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(title="chat", participant_ids=[alice.id])
    return relay_service, messages, conversation.id, alice.id


def test_enqueue_message_relay_is_idempotent(tmp_path: Path) -> None:
    """Reuse the same relay task when idempotency_key repeats."""
    relay_service, messages, conversation_id, alice_id = _build_fixture(tmp_path)
    message = messages.create_message(
        conversation_id=conversation_id,
        sender_user_id=alice_id,
        content="hello",
    )

    first = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-1",
        sender_user_id=alice_id,
    )
    second = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-1",
        sender_user_id=alice_id,
    )

    assert first.created is True
    assert second.created is False
    assert first.relay_task.relay_task_id == second.relay_task.relay_task_id
    assert first.relay_task.payload["message"]["id"] == message.id


def test_apply_delivery_receipt_updates_task_status(tmp_path: Path) -> None:
    """Persist sent/completed receipt states on relay tasks."""
    relay_service, messages, conversation_id, alice_id = _build_fixture(tmp_path)
    message = messages.create_message(
        conversation_id=conversation_id,
        sender_user_id=alice_id,
        content="hello",
    )
    created = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-2",
        sender_user_id=alice_id,
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
