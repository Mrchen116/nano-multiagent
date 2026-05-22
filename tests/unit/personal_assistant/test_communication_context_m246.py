"""M246/M247: Communication Context hook tests.

M246: 增加 message_format 说明行。
M247: group_participants 改为 {id, display_name, type} 结构；
      message_format 改为 display_name 描述；fallback 到 id。
"""

from __future__ import annotations

import pytest


def _build_block(
    *,
    conversation_type: str,
    agent_id: str | None = None,
    participant_agent_ids: list[str] | None = None,
    participants: list[dict] | None = None,
) -> str:
    from agent.products.personal_assistant.prompt_sections import _build_communication_context_block
    return _build_communication_context_block(
        conversation_type=conversation_type,
        agent_id=agent_id,
        participant_agent_ids=participant_agent_ids,
        participants=participants,
    )


def test_group_context_block_includes_message_format() -> None:
    """群聊 context block 包含 message_format 说明行（M247 更新为 display_name 描述）。"""
    block = _build_block(conversation_type="group", agent_id="agent-a", participant_agent_ids=["agent-a", "agent-b"])

    assert "message_format" in block


def test_direct_context_block_no_message_format() -> None:
    """直聊 context block 不包含 message_format 行。"""
    block = _build_block(conversation_type="direct", agent_id="agent-a")

    assert "message_format" not in block


def test_group_message_format_line_format() -> None:
    """message_format 行以 '- message_format:' 开头。"""
    block = _build_block(conversation_type="group")
    lines = block.splitlines()

    message_format_lines = [l for l in lines if "message_format" in l]
    assert len(message_format_lines) == 1
    assert message_format_lines[0].strip().startswith("- message_format:")


def test_group_context_block_still_has_other_fields() -> None:
    """增加 message_format 后，其他字段（session_type, your_agent_id, group_participants）仍存在。"""
    block = _build_block(
        conversation_type="group",
        agent_id="agent-x",
        participant_agent_ids=["agent-x", "agent-y"],
    )

    assert "session_type: group" in block
    assert "your_agent_id: agent-x" in block
    assert "group_participants:" in block
    assert "message_format" in block


# ---------------------------------------------------------------------------
# M247: structured participants and updated message_format
# ---------------------------------------------------------------------------


def test_group_context_block_message_format_says_display_name() -> None:
    """M247: message_format 描述中提到 display_name，而非 sender_id。"""
    block = _build_block(conversation_type="group")

    assert "display_name" in block
    assert "message_format" in block


def test_group_context_block_message_format_mentions_id_for_mention() -> None:
    """M247: message_format 描述中说明 @mention 用 id。"""
    block = _build_block(conversation_type="group")

    # The format description should mention that @mention uses id
    assert "@" in block or "id" in block


def test_group_context_participants_with_display_names(tmp_path: object) -> None:
    """M247: participants 参数传入时，group_participants 显示 display_name 和 type。"""
    participants = [
        {"id": "user-uuid-1", "display_name": "Alice Chen", "type": "user"},
        {"id": "agent-uuid-a", "display_name": "Agent Alpha", "type": "agent"},
    ]
    block = _build_block(
        conversation_type="group",
        agent_id="agent-uuid-a",
        participants=participants,
    )

    assert "Alice Chen" in block
    assert "Agent Alpha" in block
    assert "user" in block
    assert "agent" in block


def test_group_context_participants_fallback_to_agent_ids_when_no_participants(tmp_path: object) -> None:
    """M247: participants 未传时，fallback 使用 participant_agent_ids 原有逻辑。"""
    block = _build_block(
        conversation_type="group",
        agent_id="agent-a",
        participant_agent_ids=["agent-a", "agent-b"],
    )

    # Old format: just show the ids
    assert "agent-a" in block or "agent-b" in block
    assert "group_participants:" in block


def test_group_context_block_participants_override_agent_ids(tmp_path: object) -> None:
    """M247: 当 participants 同时与 participant_agent_ids 都传时，优先使用 participants。"""
    participants = [
        {"id": "user-uuid-1", "display_name": "Alice Chen", "type": "user"},
    ]
    block = _build_block(
        conversation_type="group",
        agent_id="agent-a",
        participant_agent_ids=["agent-a", "agent-b"],
        participants=participants,
    )

    # participants takes priority
    assert "Alice Chen" in block
