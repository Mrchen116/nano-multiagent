"""Behavior tests for the PA communication context passed to the model."""

from __future__ import annotations

from personal_assistant.product import build_communication_context_block


def test_direct_context_omits_group_only_protocol() -> None:
    block = build_communication_context_block(
        conversation_type="direct",
        agent_id="agent-a",
        participant_agent_ids=None,
    )

    assert "session_type: direct" in block
    assert "group_participants" not in block
    assert "message_format" not in block


def test_group_context_exposes_typed_participant_identities() -> None:
    block = build_communication_context_block(
        conversation_type="group",
        agent_id="Arch",
        participant_agent_ids=None,
        participants=[
            {
                "type": "agent",
                "agent_id": "ArchA",
                "user_id": "u_aaaaaaaa",
                "display_name": "Q",
            },
            {"type": "user", "user_id": "user-1", "display_name": "Alice"},
        ],
    )

    assert "session_type: group" in block
    assert "your_agent_id" not in block
    assert "user_id: u_aaaaaaaa" in block
    assert "user_id: user-1" in block
    assert "Q" in block
    assert "Alice" in block


def test_group_context_teaches_inline_mentions_for_known_participants() -> None:
    block = build_communication_context_block(
        conversation_type="group",
        agent_id="Arch",
        participant_agent_ids=None,
        participants=[
            {
                "type": "agent",
                "agent_id": "ArchA",
                "user_id": "u_aaaaaaaa",
                "display_name": "Q",
            },
            {"type": "user", "user_id": "user-1", "display_name": "Alice"},
        ],
    )

    assert '<mention type="agent"' not in block
    assert '<mention type="user" target_id="u_..."/>' in block


def test_group_context_identifies_self_by_chat_user_id():
    block = build_communication_context_block(
        conversation_type="group",
        agent_id="worker",
        participant_agent_ids=None,
        participants=[
            {
                "type": "agent",
                "agent_id": "worker",
                "user_id": "u_worker00",
                "display_name": "Worker",
            }
        ],
    )
    assert "your_user_id: u_worker00" in block
    assert "your_name: Worker" in block
    assert "agent_id:" not in block
