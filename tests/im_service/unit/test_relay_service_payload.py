"""Unit tests for relay payload structure: attachments, sender/participants fields."""

import json
from pathlib import Path

from IM.application.relay_service import RelayService
from IM.domain.models import Attachment
from IM.infra.db import connect, initialize_schema
from IM.repositories import (
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


def test_relay_payload_with_attachments_is_json_serializable(tmp_path: Path) -> None:
    """Attachment dataclass objects must be serialized to dicts before json.dumps (regression for 500 on image send)."""
    relay_service, messages, conversations, users, _profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="chat", participant_ids=[alice.id]
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="look at this image",
        attachments=[
            Attachment(
                url="http://im.local/im/uploads/abc123.png",
                content_type="image/png",
                file_name="screenshot.png",
            ),
            Attachment(
                url="http://im.local/im/uploads/def456.jpg",
                content_type="image/jpeg",
                file_name=None,
            ),
        ],
    )

    result = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-img",
        sender_user_id=alice.id,
    )

    # The payload must be valid JSON (no TypeError from unserializable dataclasses).
    payload = result.relay_task.payload
    serialized = json.dumps(payload)
    deserialized = json.loads(serialized)

    attachments = deserialized["message"]["attachments"]
    assert isinstance(attachments, list)
    assert len(attachments) == 2
    assert attachments[0]["url"] == "http://im.local/im/uploads/abc123.png"
    assert attachments[0]["content_type"] == "image/png"
    assert attachments[0]["file_name"] == "screenshot.png"
    assert attachments[1]["url"] == "http://im.local/im/uploads/def456.jpg"
    assert attachments[1]["content_type"] == "image/jpeg"
    assert attachments[1]["file_name"] is None


def test_relay_payload_without_attachments_has_empty_list(tmp_path: Path) -> None:
    """Relay payload always includes an attachments list even when message has none."""
    relay_service, messages, conversations, users, _profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(
        title="chat", participant_ids=[alice.id]
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="plain text message",
    )

    result = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-plain",
        sender_user_id=alice.id,
    )

    attachments = result.relay_task.payload["message"]["attachments"]
    assert attachments == []


# ---------------------------------------------------------------------------
# M247: sender/participants display name propagation
# ---------------------------------------------------------------------------


def test_group_relay_payload_includes_sender_display_name_and_participants(
    tmp_path: Path,
) -> None:
    """Group relay payload must carry sender.display_name and a participants list with display names."""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice Chen")
    agent_a_user = users.create_user(
        username="agent:agent-a", display_name="Agent A Display"
    )
    agent_b_user = users.create_user(
        username="agent:agent-b", display_name="Agent B Display"
    )
    profiles.upsert_profile(
        agent_id="agent-a",
        owner_id=alice.owner_id,
        display_name="Agent A Title",
        description="agent a",
        system_prompt="You are agent-a.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=None,
    )
    profiles.upsert_profile(
        agent_id="agent-b",
        owner_id=alice.owner_id,
        display_name="Agent B Title",
        description="agent b",
        system_prompt="You are agent-b.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=None,
    )
    conversation = conversations.create_conversation(
        title="group chat",
        participant_ids=[alice.id, agent_a_user.id, agent_b_user.id],
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="@agent-a hello",
    )

    result = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-m247-sender",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    payload = result.relay_task.payload
    # sender must contain user_id, display_name, type
    sender = payload["sender"]
    assert sender["user_id"] == alice.id
    assert sender["display_name"] == "Alice Chen"
    assert sender["type"] == "user"
    # participants must list all members with display_name and type
    participants = payload["participants"]
    alice_entry = next(p for p in participants if p["user_id"] == alice.id)
    assert alice_entry["display_name"] == "Alice Chen"
    assert alice_entry["type"] == "user"
    # agent participants resolved from agent_profiles.display_name
    agent_entries = [p for p in participants if p["type"] == "agent"]
    assert len(agent_entries) == 2
    agent_names = {p["display_name"] for p in agent_entries}
    assert "Agent A Title" in agent_names
    assert "Agent B Title" in agent_names


def test_group_relay_payload_sender_fallback_to_id_when_no_user_record(
    tmp_path: Path,
) -> None:
    """Sender display_name falls back to sender_user_id when the user is unknown."""
    relay_service, messages, conversations, users, _profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice Chen")
    conversation = conversations.create_conversation(
        title="group chat",
        participant_ids=[alice.id],
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello",
    )
    unknown_sender_id = "unknown-user-uuid"

    result = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-m247-fallback",
        sender_user_id=unknown_sender_id,
        conversation_type="group",
    )

    payload = result.relay_task.payload
    sender = payload["sender"]
    assert sender["user_id"] == unknown_sender_id
    # fallback: display_name equals the raw id when no user record found
    assert sender["display_name"] == unknown_sender_id


def test_direct_relay_payload_does_not_include_sender_participants(
    tmp_path: Path,
) -> None:
    """Direct relay payloads must NOT include sender/participants fields (backward compat)."""
    relay_service, messages, conversations, users, _profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice Chen")
    conversation = conversations.create_conversation(
        title="direct chat",
        participant_ids=[alice.id],
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello",
    )

    result = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-m247-direct",
        sender_user_id=alice.id,
        conversation_type="direct",
    )

    payload = result.relay_task.payload
    assert "sender" not in payload
    assert "participants" not in payload
