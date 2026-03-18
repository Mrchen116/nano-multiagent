"""Built-in hook defaults and product-level hook setup for personal_assistant."""

from __future__ import annotations

from typing import Any, Mapping

DEFAULT_HOOK_MODULES = ["default_status", "usage_metrics"]

__all__ = ["DEFAULT_HOOK_MODULES", "setup", "_build_communication_context_block"]


def _build_communication_context_block(
    *,
    conversation_type: str,
    agent_id: str | None,
    participant_agent_ids: list[str] | None,
) -> str:
    """Build a communication context block for injection into the system prompt.

    Args:
        conversation_type: "group" or "direct".
        agent_id: This agent's id, used to identify itself in the context block.
        participant_agent_ids: Other agent ids in a group chat; ignored for direct chats.

    Returns:
        A newline-delimited context block string starting with ``[Communication Context]``.

    Notes:
        Group chats include the full participant list; direct chats omit it to
        keep the prompt concise. The block is appended AFTER the existing system
        prompt so it does not alter the agent's core persona.
    """

    lines = ["[Communication Context]", f"- session_type: {conversation_type}"]
    if agent_id:
        lines.append(f"- your_agent_id: {agent_id}")
    if conversation_type == "group" and participant_agent_ids is not None:
        ids_repr = ", ".join(participant_agent_ids) if participant_agent_ids else "(none)"
        lines.append(f"- group_participants: {ids_repr}")
    return "\n".join(lines)


def setup(hooks: Any) -> None:  # noqa: ANN401
    """Register the personal_assistant product-level before_agent_start hook.

    The hook reads ``ctx.metadata`` for ``conversation_type``, ``agent_id``, and
    ``participant_agent_ids``, then appends a communication context block to the
    system prompt.  When ``conversation_type`` is absent the hook returns ``None``
    and is effectively a no-op (safe degradation for sessions created without
    group metadata).

    Args:
        hooks: ``HookAPI`` instance provided by the loader at startup; used to
            register event handlers.
    """

    def _before_agent_start(payload: Mapping[str, Any], ctx: Any) -> dict[str, Any] | None:
        """Append communication context to system prompt on session start.

        Args:
            payload: Hook payload containing ``message`` and ``system_prompt`` keys.
            ctx: ``HookContext`` carrying ``session_id`` and runtime metadata. The
                keys ``conversation_type``, ``agent_id``, and ``participant_agent_ids``
                must be present in ``ctx.metadata`` for the hook to act; otherwise the
                hook returns ``None`` to preserve existing runtime behaviour.

        Returns:
            Dict with ``system_prompt`` key containing the enriched prompt, or
            ``None`` when ``conversation_type`` is absent in the hook context metadata.
        """
        metadata: Mapping[str, Any] = getattr(ctx, "metadata", {}) or {}
        conversation_type = metadata.get("conversation_type")
        if not isinstance(conversation_type, str) or not conversation_type:
            # conversation_type missing — this session was created without group metadata;
            # returning None preserves the existing frozen_system_prompt fallback.
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
        if isinstance(base_prompt, str) and base_prompt.strip():
            enriched = base_prompt.rstrip() + "\n\n" + context_block
        else:
            enriched = context_block

        return {"system_prompt": enriched}

    hooks.on("before_agent_start", _before_agent_start, priority=200, timeout_ms=500)
