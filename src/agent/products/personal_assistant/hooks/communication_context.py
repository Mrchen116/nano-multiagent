"""Communication context helpers for personal_assistant.

The before_agent_start hook that used to inject a system_prompt override with
the [Communication Context] block has been retired in feat-379-M1.  Group-chat
context is now handled by the pa.communication_context segment (order=900,
cache_safe=False) which is assembled by assemble_system_prompt each turn and
reads scenario data from PromptContext.scenario — no hook side-channel needed.

_build_communication_context_block is kept here (not deleted) because:
  1. It carries the bugfix-358 mention-tag format verbatim.
  2. prompt_sections.py::_render_communication_context imports it to avoid
     duplicating the exact text that regression tests verify character-for-character.
"""

from __future__ import annotations

from typing import Any, Mapping

# auto_mode_gate added in feat-333 (unified allow/deny/ask classifier).
# self_improvement added in feat-349-M3: background self-evolution hook.
DEFAULT_HOOK_MODULES = ["auto_mode_gate", "communication_context", "default_status", "usage_metrics", "chat_history", "realtime_stream", "self_improvement"]


def _build_communication_context_block(
    *,
    conversation_type: str,
    agent_id: str | None,
    participant_agent_ids: list[str] | None,
    participants: list[dict[str, str]] | None = None,
) -> str:
    """Build the [Communication Context] block injected into system prompts.

    Args:
        conversation_type: Conversation kind (``"group"`` or ``"direct"``).
        agent_id: This agent's own ID, injected as ``your_agent_id``.
        participant_agent_ids: Fallback list of agent IDs when structured
            ``participants`` data is unavailable (pre-M247 sessions).
        participants: Structured participant list with actor-first identity fields.
            User entries should carry ``user_id`` and agent entries should carry
            ``agent_id``. Legacy ``id`` is still accepted as fallback.
            When provided, takes priority over ``participant_agent_ids``.

    Returns:
        Multi-line context block string ready for system prompt injection.
    """
    lines = ["[Communication Context]", f"- session_type: {conversation_type}"]
    if agent_id:
        lines.append(f"- your_agent_id: {agent_id}")
    if conversation_type == "group":
        if participants is not None:
            # Structured participant list with actor-first IDs.
            if participants:
                entries = []
                for p in participants:
                    p_type = p.get("type", "user")
                    if p_type == "agent":
                        identity_key = "agent_id"
                        p_identity = p.get("agent_id") or p.get("id", "")
                    elif p_type == "user":
                        identity_key = "user_id"
                        p_identity = p.get("user_id") or p.get("id", "")
                    else:
                        identity_key = "id"
                        p_identity = p.get("id", "")
                    p_display = p.get("display_name") or p_identity or "unknown"
                    if p_identity:
                        entries.append(f"{p_display} ({p_type}, {identity_key}: {p_identity})")
                    else:
                        entries.append(f"{p_display} ({p_type})")
                lines.append(f"- group_participants: {'; '.join(entries)}")
            else:
                lines.append("- group_participants: (none)")
        elif participant_agent_ids is not None:
            # Fallback for pre-M247 sessions that only carry agent ID lists.
            ids_repr = ", ".join(participant_agent_ids) if participant_agent_ids else "(none)"
            lines.append(f"- group_participants: {ids_repr}")
        # bugfix-358: message_format 改为教 inline mention 标签，不再教 @agent_id 形式。
        # target_id 严格取自上方 group_participants 对应条目的 agent_id / user_id。
        lines.append(
            "- message_format: 历史消息中每条以 [display_name] 标识发言人；你的回复无需加前缀。"
            ' 在群聊中引用某人时，直接在回复中写 <mention type="agent" target_id="<id>"/> 或'
            ' <mention type="user" target_id="<id>"/>，'
            " <id> 严格取自上方 group_participants 对应条目的 agent_id / user_id。"
            ' 例：<mention type="agent" target_id="ArchA"/> 你说呢？'
            ' / <mention type="user" target_id="user-uuid"/> 我同意。'
            " 在当前会话中回应时直接输出文本，不要调用 send_message；"
            "仅当目标不在当前会话（私聊用户/触达其他 agent/发送到其他群）时，使用 send_message(to=user_id|agent_id|conversation_id)。"
        )
    return "\n".join(lines)


def setup(hooks: Any) -> None:  # noqa: ANN401
    # feat-379-M1: before_agent_start prompt injection retired.
    # Previously this handler built a [Communication Context] block and appended
    # it to the system prompt via the hook side-channel. That mechanism is
    # superseded by the pa.communication_context segment (order=900) which is
    # assembled by assemble_system_prompt from PromptContext.scenario each turn.
    # The hook registration is intentionally removed; other hooks that listen on
    # before_agent_start (e.g. auto_mode_gate, default_status) are unaffected.
    pass
