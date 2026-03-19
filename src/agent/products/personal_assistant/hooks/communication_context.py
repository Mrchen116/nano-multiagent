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
        participants: M247 structured participant list; each item has
            ``id``, ``display_name``, and ``type`` (``"user"``/``"agent"``).
            When provided, takes priority over ``participant_agent_ids``.

    Returns:
        Multi-line context block string ready for system prompt injection.
    """
    lines = ["[Communication Context]", f"- session_type: {conversation_type}"]
    if agent_id:
        lines.append(f"- your_agent_id: {agent_id}")
    if conversation_type == "group":
        if participants is not None:
            # M247: structured participant list with display names and types.
            # Each entry: "display_name (type, id: <id>)" for unambiguous attribution.
            if participants:
                entries = []
                for p in participants:
                    p_display = p.get("display_name") or p.get("id", "unknown")
                    p_type = p.get("type", "user")
                    p_id = p.get("id", "")
                    entries.append(f"{p_display} ({p_type}, id: {p_id})")
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
            "你的回复无需加前缀。如需 @mention 某人，使用其 id（如 @agent_id）。"
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
