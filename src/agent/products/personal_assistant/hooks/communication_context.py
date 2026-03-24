"""Group/direct communication context injection for personal_assistant."""

from __future__ import annotations

from typing import Any, Mapping

DEFAULT_HOOK_MODULES = ["communication_context", "default_status", "usage_metrics", "chat_history"]


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
        # M247: message_format updated to reference display_name for readability.
        # @mention still uses id for routing precision.
        lines.append(
            "- message_format: 历史消息中每条以 [display_name] 标识发言人；"
            "你的回复无需加前缀。群聊中如需 @mention Agent，使用其 agent_id（如 @agent_id）；"
            "在当前会话中回应时直接输出文本，不要调用 send_message；"
            "仅当目标不在当前会话（私聊用户/触达其他 agent/发送到其他群）时，使用 send_message(to=user_id|agent_id|conversation_id)。"
        )
    return "\n".join(lines)


def setup(hooks: Any) -> None:  # noqa: ANN401
    def _before_agent_start(payload: Mapping[str, Any], ctx: Any) -> dict[str, Any] | None:
        metadata: Mapping[str, Any] = getattr(ctx, "metadata", {}) or {}
        conversation_type = metadata.get("conversation_type")
        if not isinstance(conversation_type, str) or not conversation_type:
            return None

        agent_id = metadata.get("agent_id")
        if not isinstance(agent_id, str):
            agent_id = None

        # M247: prefer structured participants list over flat agent-id list.
        raw_participants = metadata.get("participants")
        participants: list[dict[str, str]] | None = None
        if isinstance(raw_participants, list):
            participants = [dict(p) for p in raw_participants if isinstance(p, dict)]

        raw_agent_ids = metadata.get("participant_agent_ids")
        participant_agent_ids: list[str] | None = None
        if isinstance(raw_agent_ids, list):
            participant_agent_ids = [str(p) for p in raw_agent_ids if isinstance(p, str)]

        context_block = _build_communication_context_block(
            conversation_type=conversation_type,
            agent_id=agent_id,
            participant_agent_ids=participant_agent_ids,
            participants=participants,
        )

        base_prompt = payload.get("system_prompt")
        if not isinstance(base_prompt, str) or not base_prompt.strip():
            session_prompt = metadata.get("system_prompt")
            if isinstance(session_prompt, str) and session_prompt.strip():
                base_prompt = session_prompt
        if isinstance(base_prompt, str) and base_prompt.strip():
            enriched = base_prompt.rstrip() + "\n\n" + context_block
        else:
            enriched = context_block

        return {"system_prompt": enriched}

    hooks.on("before_agent_start", _before_agent_start, priority=200, timeout_ms=500)
