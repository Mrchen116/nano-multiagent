"""Group/direct communication context injection for personal_assistant."""

from __future__ import annotations

from typing import Any, Mapping

DEFAULT_HOOK_MODULES = ["communication_context", "default_status", "usage_metrics"]


def _build_communication_context_block(
    *,
    conversation_type: str,
    agent_id: str | None,
    participant_agent_ids: list[str] | None,
) -> str:
    lines = ["[Communication Context]", f"- session_type: {conversation_type}"]
    if agent_id:
        lines.append(f"- your_agent_id: {agent_id}")
    if conversation_type == "group" and participant_agent_ids is not None:
        ids_repr = ", ".join(participant_agent_ids) if participant_agent_ids else "(none)"
        lines.append(f"- group_participants: {ids_repr}")
    if conversation_type == "group":
        # M246: each group message is prefixed with the sender identifier so the model
        # can attribute messages to their authors.  Direct chats need no such hint.
        lines.append("- message_format: [sender_id] message_text")
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

        raw_participants = metadata.get("participant_agent_ids")
        participant_agent_ids: list[str] | None = None
        if isinstance(raw_participants, list):
            participant_agent_ids = [str(p) for p in raw_participants if isinstance(p, str)]

        context_block = _build_communication_context_block(
            conversation_type=conversation_type,
            agent_id=agent_id,
            participant_agent_ids=participant_agent_ids,
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
