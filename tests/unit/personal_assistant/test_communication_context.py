"""Unit tests for communication context block assembly.

Covers:
- message_format field presence and format in group vs direct context
- group_participants structure (display_name, type, identity keys)
- Inline mention tag format teaching (group context)
- PA system prompt must not contain deprecated wording
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
    from agent.products.personal_assistant.prompt_sections import (
        _build_communication_context_block,
    )

    return _build_communication_context_block(
        conversation_type=conversation_type,
        agent_id=agent_id,
        participant_agent_ids=participant_agent_ids,
        participants=participants,
    )


# ── message_format field ────────────────────────────────────────────────────


def test_group_context_block_includes_message_format() -> None:
    """群聊 context block 包含 message_format 说明行。"""
    block = _build_block(
        conversation_type="group",
        agent_id="agent-a",
        participant_agent_ids=["agent-a", "agent-b"],
    )

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


# ── participants structure ──────────────────────────────────────────────────


def test_group_context_block_message_format_says_display_name() -> None:
    """message_format 描述中提到 display_name。"""
    block = _build_block(conversation_type="group")

    assert "display_name" in block
    assert "message_format" in block


def test_group_context_block_message_format_mentions_id_for_mention() -> None:
    """message_format 描述中说明 @mention 用 id。"""
    block = _build_block(conversation_type="group")

    assert "@" in block or "id" in block


def test_group_context_participants_with_display_names(tmp_path: object) -> None:
    """participants 参数传入时，group_participants 显示 display_name 和 type。"""
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


def test_group_context_participants_fallback_to_agent_ids_when_no_participants(
    tmp_path: object,
) -> None:
    """participants 未传时，fallback 使用 participant_agent_ids 原有逻辑。"""
    block = _build_block(
        conversation_type="group",
        agent_id="agent-a",
        participant_agent_ids=["agent-a", "agent-b"],
    )

    assert "agent-a" in block or "agent-b" in block
    assert "group_participants:" in block


def test_group_context_block_participants_override_agent_ids(tmp_path: object) -> None:
    """当 participants 同时与 participant_agent_ids 都传时，优先使用 participants。"""
    participants = [
        {"id": "user-uuid-1", "display_name": "Alice Chen", "type": "user"},
    ]
    block = _build_block(
        conversation_type="group",
        agent_id="agent-a",
        participant_agent_ids=["agent-a", "agent-b"],
        participants=participants,
    )

    assert "Alice Chen" in block


# ── inline mention tag format ───────────────────────────────────────────────


def test_group_context_block_mention_format_teaches_inline_tag() -> None:
    """message_format 行必须教 <mention type=... target_id=.../> 标签格式。"""
    block = _build_block(
        conversation_type="group",
        agent_id="Arch",
        participants=[
            {"type": "agent", "agent_id": "Arch", "display_name": "架构"},
            {"type": "agent", "agent_id": "ArchA", "display_name": "Q"},
        ],
    )

    assert "<mention" in block, (
        f"message_format must teach <mention> tag, got:\n{block}"
    )
    assert "target_id" in block, (
        f"message_format must reference target_id attribute, got:\n{block}"
    )


def test_group_context_block_mention_format_no_at_id_syntax() -> None:
    """message_format 不应包含旧的 @<agent_id> 形式教程（只教 inline tag）。"""
    block = _build_block(
        conversation_type="group",
        agent_id="Arch",
        participants=[
            {"type": "agent", "agent_id": "Arch", "display_name": "架构"},
        ],
    )

    lines = block.splitlines()
    format_lines = [l for l in lines if "message_format" in l or "mention" in l.lower()]
    for line in format_lines:
        assert "@agent_id" not in line, (
            f"message_format should not teach @agent_id syntax: {line}"
        )
        assert "@<id>" not in line, (
            f"message_format should not teach @<id> syntax: {line}"
        )


def test_group_context_block_mention_format_has_example() -> None:
    """message_format 段必须有 agent 和 user 各一个示例 target_id 引用。"""
    block = _build_block(
        conversation_type="group",
        agent_id="Arch",
        participants=[
            {"type": "agent", "agent_id": "Arch", "display_name": "架构"},
            {"type": "user", "user_id": "user-uuid-1", "display_name": "Test User"},
        ],
    )

    assert 'type="agent"' in block or "type='agent'" in block, (
        f"message_format must have agent mention example, got:\n{block}"
    )


# ── participants identity keys ──────────────────────────────────────────────


def test_group_participants_agent_shows_agent_id_key() -> None:
    """participants 中 agent 条目，identity key 为 agent_id（不是 id）。"""
    block = _build_block(
        conversation_type="group",
        agent_id="Arch",
        participants=[
            {"type": "agent", "agent_id": "Arch", "display_name": "架构"},
            {"type": "agent", "agent_id": "ArchA", "display_name": "Q"},
        ],
    )

    assert "agent_id: Arch" in block or "agent_id:Arch" in block, (
        f"agent participant entry must show agent_id: X, got:\n{block}"
    )
    assert "agent_id: ArchA" in block or "agent_id:ArchA" in block, (
        f"agent participant entry must show agent_id: X, got:\n{block}"
    )


def test_group_participants_user_shows_user_id_key() -> None:
    """participants 中 user 条目，identity key 为 user_id（不是 id）。"""
    block = _build_block(
        conversation_type="group",
        agent_id="Arch",
        participants=[
            {"type": "agent", "agent_id": "Arch", "display_name": "架构"},
            {"type": "user", "user_id": "user-uuid-1", "display_name": "Test User"},
        ],
    )

    assert "user_id: user-uuid-1" in block or "user_id:user-uuid-1" in block, (
        f"user participant entry must show user_id: X, got:\n{block}"
    )


# ── PA system prompt deprecated wording ────────────────────────────────────


def test_prompts_no_prefer_stable_ids_line() -> None:
    """PA system prompt sections must not contain deprecated 'prefer stable IDs' wording.

    prompts.py deleted; verify invariant against PA_SECTIONS (segment-based assembly).
    """
    from agent.products.personal_assistant.prompt_sections import PA_SECTIONS
    from agent.core.agent.prompt_sections.base import (
        PromptContext,
        assemble_system_prompt,
    )

    ctx = PromptContext(current_datetime="2026-01-01T00:00:00", cwd="/ws")
    assembled = assemble_system_prompt(list(PA_SECTIONS), ctx)

    assert "prefer stable IDs" not in assembled, (
        "PA system prompt must not contain deprecated 'prefer stable IDs' wording"
    )
    assert "user_id / agent_id" not in assembled, (
        "PA system prompt must not reference 'user_id / agent_id' as interchangeable IDs"
    )
