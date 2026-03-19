"""M246: Communication Context 增加 message_format 说明行测试。"""

from __future__ import annotations

import pytest


def _build_block(*, conversation_type: str, agent_id: str | None = None, participant_agent_ids: list[str] | None = None) -> str:
    from agent.products.personal_assistant.hooks.communication_context import _build_communication_context_block
    return _build_communication_context_block(
        conversation_type=conversation_type,
        agent_id=agent_id,
        participant_agent_ids=participant_agent_ids,
    )


def test_group_context_block_includes_message_format() -> None:
    """群聊 context block 包含 message_format 说明行。"""
    block = _build_block(conversation_type="group", agent_id="agent-a", participant_agent_ids=["agent-a", "agent-b"])

    assert "message_format" in block
    assert "[sender_id] message_text" in block


def test_direct_context_block_no_message_format() -> None:
    """直聊 context block 不包含 message_format 行。"""
    block = _build_block(conversation_type="direct", agent_id="agent-a")

    assert "message_format" not in block


def test_group_message_format_line_format() -> None:
    """message_format 行符合 '- message_format: [sender_id] message_text' 格式。"""
    block = _build_block(conversation_type="group")
    lines = block.splitlines()

    message_format_lines = [l for l in lines if "message_format" in l]
    assert len(message_format_lines) == 1
    assert message_format_lines[0].strip().startswith("- message_format:")
    assert "[sender_id] message_text" in message_format_lines[0]


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
