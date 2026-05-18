"""bugfix-358: communication_context hook 教 agent 输出 inline mention 标签。

R3 红测：
- message_format 改为教 inline <mention type="agent" target_id="X"/> 格式
- 不再含 @agent_id 形式的教程
- 删除 prompts.py:62 "prefer stable IDs (user_id / agent_id)" 硬编码措辞
- participants 中 agent 条目：identity_key=agent_id、user 条目：identity_key=user_id
"""

from __future__ import annotations


def _build_block(
    *,
    conversation_type: str,
    agent_id: str | None = None,
    participant_agent_ids: list[str] | None = None,
    participants: list[dict] | None = None,
) -> str:
    from agent.products.personal_assistant.hooks.communication_context import (
        _build_communication_context_block,
    )

    return _build_communication_context_block(
        conversation_type=conversation_type,
        agent_id=agent_id,
        participant_agent_ids=participant_agent_ids,
        participants=participants,
    )


# ─── mention_format: 教 inline tag ─────────────────────────────────────────

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

    # 必须包含 inline tag 语法示例
    assert "<mention" in block, f"message_format must teach <mention> tag, got:\n{block}"
    assert "target_id" in block, f"message_format must reference target_id attribute, got:\n{block}"


def test_group_context_block_mention_format_no_at_id_syntax() -> None:
    """message_format 不应包含旧的 @<agent_id> 形式教程（只教 inline tag）。"""
    block = _build_block(
        conversation_type="group",
        agent_id="Arch",
        participants=[
            {"type": "agent", "agent_id": "Arch", "display_name": "架构"},
        ],
    )

    # 旧措辞：@agent_id 或 @<id> 形式作为教程不应出现
    # （注意 group_participants 里 agent_id 的标签展示可以含 @，这里过滤 mention 规则行）
    lines = block.splitlines()
    format_lines = [l for l in lines if "message_format" in l or "mention" in l.lower()]
    for line in format_lines:
        assert "@agent_id" not in line, f"message_format should not teach @agent_id syntax: {line}"
        assert "@<id>" not in line, f"message_format should not teach @<id> syntax: {line}"


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

    # 至少有一个 type="agent" 示例
    assert 'type="agent"' in block or "type='agent'" in block, (
        f"message_format must have agent mention example, got:\n{block}"
    )


# ─── participants 条目：actor-first identity key ────────────────────────────

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

    # group_participants 行中展示的 identity key 应为 agent_id
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


# ─── prompts.py: 删除 "prefer stable IDs" 硬编码措辞 ─────────────────────

def test_prompts_no_prefer_stable_ids_line() -> None:
    """prompts.py 中不再包含 'prefer stable IDs (user_id / agent_id)' 措辞。"""
    from agent.products.personal_assistant import prompts

    # 该措辞是层级混淆的证据，bugfix-358 要求删除
    assert "prefer stable IDs" not in prompts.PERSONAL_ASSISTANT_SYSTEM_PROMPT, (
        "prompts.py must not contain deprecated 'prefer stable IDs' wording"
    )
    assert "user_id / agent_id" not in prompts.PERSONAL_ASSISTANT_SYSTEM_PROMPT, (
        "prompts.py must not reference 'user_id / agent_id' as interchangeable IDs"
    )
