"""Unit tests for group relay mention routing and profile version advancement."""

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


def test_enqueue_message_relay_targets_the_mentioned_agent_in_group_chats(
    tmp_path: Path,
) -> None:
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
    # bugfix-358: mention format changed from "@agent-b" text to XML tag.
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content='<mention type="agent" target_id="agent-b"/> please reply in thread',
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


def test_enqueue_message_relay_advances_group_profile_version_without_overwriting_frozen_prompt(
    tmp_path: Path,
) -> None:
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
    )

    # bugfix-358: mention format changed from "@agent-a" text to XML tag.
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content='<mention type="agent" target_id="agent-a"/> please stay silent if NO_REPLY works.',
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


def test_enqueue_message_relay_uses_live_group_prompt_when_conversation_has_no_matching_frozen_prompt(
    tmp_path: Path,
) -> None:
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
    )

    # bugfix-358: mention format changed from "@agent-a" text to XML tag.
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content='<mention type="agent" target_id="agent-a"/> please stay silent if NO_REPLY works.',
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


def test_enqueue_message_relay_normalizes_typed_and_picker_mentions_to_the_same_agent(
    tmp_path: Path,
) -> None:
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
    # bugfix-358: both typed and picker mentions now use XML tag format.
    typed = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content='<mention type="agent" target_id="agent-b"/> please review the typed mention',
    )
    picker = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content='<mention type="agent" target_id="agent-b"/> please review the picker mention',
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
    assert typed_relay.relay_task.payload["metadata"]["mentioned_agent_ids"] == [
        "agent-b"
    ]
    assert picker_relay.relay_task.payload["metadata"]["mentioned_agent_ids"] == [
        "agent-b"
    ]
