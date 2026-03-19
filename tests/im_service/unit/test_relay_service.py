"""Unit tests for IM relay task orchestration."""

import json
from pathlib import Path

from IM.application.relay_service import RelayService
from IM.domain.models import Attachment
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


def test_direct_conversation_relay_keeps_old_snapshot_while_new_conversation_uses_updated_profile(tmp_path: Path) -> None:
    """Freeze old direct-chat relay metadata after profile edits while new direct chats use the latest config."""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_alias = users.create_user(username="agent:agent-a", display_name="Agent A Alias")
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
        workspace_root=None,
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


def test_enqueue_message_relay_targets_the_mentioned_agent_in_group_chats(tmp_path: Path) -> None:
    """Group relay payloads must snapshot the addressed agent even when the mention includes punctuation."""
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
        workspace_root=None,
    )
    profiles.upsert_profile(
        agent_id="agent-b",
        owner_id=alice.owner_id,
        display_name="Agent B",
        description="profile b",
        system_prompt="You are agent-b.",
        skills=["playwright", "tdd-execution-worker"],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    conversation = conversations.create_conversation(
        title="group",
        participant_ids=[alice.id, agent_a_user.id, agent_b_user.id],
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="@agent-b, please reply in thread",
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
        "participant_agent_ids": ["agent-a", "agent-b"],
        "config_profile_version": 1,
    }


def test_enqueue_message_relay_advances_group_profile_version_without_overwriting_frozen_prompt(tmp_path: Path) -> None:
    """Group relays must advance to the latest mentioned-agent profile version while keeping the matching prompt snapshot."""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    agent_a_user = users.create_user(username="agent:agent-a", display_name="Agent A")
    agent_b_user = users.create_user(username="agent:agent-b", display_name="Agent B")
    profiles.upsert_profile(
        agent_id="agent-a",
        owner_id=alice.owner_id,
        display_name="Agent A",
        description="profile a",
        system_prompt="Reply with ALPHA_ACK_M170.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
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
        workspace_root=None,
    )
    conversation = conversations.create_conversation(
        title="group",
        participant_ids=[alice.id, agent_a_user.id, agent_b_user.id],
    )

    app_prompt = "When mentioned in a group chat, reply exactly with NO_REPLY."
    connection = relay_service._connection
    with connection:
        connection.execute(
            "UPDATE conversations SET config_agent_id = ?, config_system_prompt = ? WHERE id = ?",
            ("agent-a", app_prompt, conversation.id),
        )
    profiles.update_profile(
        agent_id="agent-a",
        profile_version=1,
        display_name="Agent A",
        description="profile a v2",
        system_prompt=app_prompt,
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )

    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="@agent-a please stay silent if NO_REPLY works.",
    )

    created = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-group-live-profile",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    assert created.relay_task.payload["agent_id"] == "agent-a"
    assert created.relay_task.payload["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-a"],
        "participant_agent_ids": ["agent-a", "agent-b"],
        "config_profile_version": 2,
    }


def test_enqueue_message_relay_uses_live_group_prompt_when_conversation_has_no_matching_frozen_prompt(tmp_path: Path) -> None:
    """Group relays must keep using the live prompt when no matching frozen prompt snapshot exists."""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    agent_a_user = users.create_user(username="agent:agent-a", display_name="Agent A")
    agent_b_user = users.create_user(username="agent:agent-b", display_name="Agent B")
    profiles.upsert_profile(
        agent_id="agent-a",
        owner_id=alice.owner_id,
        display_name="Agent A",
        description="profile a",
        system_prompt="Reply with ALPHA_ACK_M170.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
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
        workspace_root=None,
    )
    conversation = conversations.create_conversation(
        title="group",
        participant_ids=[alice.id, agent_a_user.id, agent_b_user.id],
    )

    profiles.update_profile(
        agent_id="agent-a",
        profile_version=1,
        display_name="Agent A",
        description="profile a v2",
        system_prompt="When mentioned in a group chat, reply exactly with NO_REPLY.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )

    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="@agent-a please stay silent if NO_REPLY works.",
    )

    created = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="idem-group-live-profile-no-frozen-prompt",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    assert created.relay_task.payload["agent_id"] == "agent-a"
    assert created.relay_task.payload["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-a"],
        "participant_agent_ids": ["agent-a", "agent-b"],
        "config_profile_version": 2,
    }


def test_enqueue_message_relay_normalizes_typed_and_picker_mentions_to_the_same_agent(tmp_path: Path) -> None:
    """Typed and picker mention tokens must converge on the same addressed agent id."""
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
        workspace_root=None,
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
        workspace_root=None,
    )
    conversation = conversations.create_conversation(
        title="group",
        participant_ids=[alice.id, agent_a_user.id, agent_b_user.id],
    )
    typed = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="@agent-b please review the typed mention",
    )
    picker = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="@agent:agent-b please review the picker mention",
    )

    typed_relay = relay_service.enqueue_message_relay(
        message=typed,
        target_node_id="node-1",
        idempotency_key="idem-mentioned-agent-typed",
        sender_user_id=alice.id,
        conversation_type="group",
    )
    picker_relay = relay_service.enqueue_message_relay(
        message=picker,
        target_node_id="node-1",
        idempotency_key="idem-mentioned-agent-picker",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    assert typed_relay.relay_task.payload["agent_id"] == "agent-b"
    assert picker_relay.relay_task.payload["agent_id"] == "agent-b"
    assert typed_relay.relay_task.payload["metadata"]["mentioned_agent_ids"] == ["agent-b"]
    assert picker_relay.relay_task.payload["metadata"]["mentioned_agent_ids"] == ["agent-b"]


def test_relay_payload_with_attachments_is_json_serializable(tmp_path: Path) -> None:
    """Attachment dataclass objects must be serialized to dicts before json.dumps (regression for 500 on image send)."""
    relay_service, messages, conversations, users, _profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    conversation = conversations.create_conversation(title="chat", participant_ids=[alice.id])
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="look at this image",
        attachments=[
            Attachment(url="http://im.local/im/uploads/abc123.png", content_type="image/png", file_name="screenshot.png"),
            Attachment(url="http://im.local/im/uploads/def456.jpg", content_type="image/jpeg", file_name=None),
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
    conversation = conversations.create_conversation(title="chat", participant_ids=[alice.id])
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


def test_group_relay_payload_includes_sender_display_name_and_participants(tmp_path: Path) -> None:
    """Group relay payload must carry sender.display_name and a participants list with display names."""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice Chen")
    agent_a_user = users.create_user(username="agent:agent-a", display_name="Agent A Display")
    agent_b_user = users.create_user(username="agent:agent-b", display_name="Agent B Display")
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
    # sender must contain id, display_name, type
    sender = payload["sender"]
    assert sender["id"] == alice.id
    assert sender["display_name"] == "Alice Chen"
    assert sender["type"] == "user"
    # participants must list all members with display_name and type
    participants = payload["participants"]
    alice_entry = next(p for p in participants if p["id"] == alice.id)
    assert alice_entry["display_name"] == "Alice Chen"
    assert alice_entry["type"] == "user"
    # agent participants resolved from agent_profiles.display_name
    agent_entries = [p for p in participants if p["type"] == "agent"]
    assert len(agent_entries) == 2
    agent_names = {p["display_name"] for p in agent_entries}
    assert "Agent A Title" in agent_names
    assert "Agent B Title" in agent_names


def test_group_relay_payload_sender_fallback_to_id_when_no_user_record(tmp_path: Path) -> None:
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
    assert sender["id"] == unknown_sender_id
    # fallback: display_name equals the raw id when no user record found
    assert sender["display_name"] == unknown_sender_id


def test_direct_relay_payload_does_not_include_sender_participants(tmp_path: Path) -> None:
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
