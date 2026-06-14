"""Unit tests for the PA communication_context block (feat-379-M1).

Group-chat communication context is provided by the pa.communication_context
segment (group tail slot), not by a before_agent_start hook. refactor-406-M2:
products/ dissolved — the block helper lives in the PA production factory
(personal_assistant.product.build_communication_context_block); the legacy PA
before_agent_start hook is gone (build_pa_kernel uses no hooks), so the hook-
retirement tests (which asserted the退役 of a now-deleted hook) are removed.
"""

from __future__ import annotations

from personal_assistant.product import build_communication_context_block


def test_build_context_block_group_contains_required_fields() -> None:
    """Group context block contains conversation_type, agent_id, and participant list."""
    block = build_communication_context_block(
        conversation_type="group",
        agent_id="agent-a",
        participant_agent_ids=["agent-a", "agent-b"],
    )
    assert "[Communication Context]" in block
    assert "group" in block
    assert "agent-a" in block
    assert "agent-b" in block


def test_build_context_block_direct_contains_agent_id_only() -> None:
    """Direct-chat context block contains agent_id but no participant list."""
    block = build_communication_context_block(
        conversation_type="direct",
        agent_id="agent-x",
        participant_agent_ids=None,
    )
    assert "[Communication Context]" in block
    assert "direct" in block
    assert "agent-x" in block
    # Direct chat should not list participants.
    assert "participants" not in block.lower() or "[]" in block
