"""Cross-module coverage for identity-based group mention routing."""

from __future__ import annotations

from pathlib import Path

from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.users import UserRepository


def test_group_relay_routes_inline_identity_without_display_name_collision(
    tmp_path: Path,
) -> None:
    """Route to the participant ID even when another profile has the same name."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    profiles = AgentProfileRepository(connection)
    relay = RelayService(connection)

    owner = users.create_user(username="alice", display_name="Alice")
    target_user = users.create_user(
        username="agent:agent-target", display_name="Shared Name"
    )
    users.create_user(username="agent:orphan", display_name="Shared Name")
    for agent_id in ("agent-target", "orphan"):
        profiles.upsert_profile(
            agent_id=agent_id,
            owner_id=owner.owner_id,
            display_name="Shared Name",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )

    conversation = conversations.create_conversation(
        title="group",
        participant_ids=[owner.id, target_user.id],
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        content=('<mention type="agent" target_id="agent-target"/> please answer'),
    )

    results = relay.enqueue_message_relay_all(
        message=message,
        target_node_id="node-1",
        idempotency_key_base="same-name-route",
        sender_user_id=owner.id,
        conversation_type="group",
    )

    assert len(results) == 1
    payload = results[0].relay_task.payload
    assert payload["agent_id"] == "agent-target"
    assert payload["metadata"]["mentioned_agent_ids"] == ["agent-target"]
