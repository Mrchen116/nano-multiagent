"""Background hook that triggers self-evolution review forks after a nudge threshold.

Design ref: docs/changes/feat-349-self-evolving-skills-memory/design.md §5

Counter semantics (decision 2 in design.md):
- ``tool_iterations`` payload field is the session-lifetime tool iteration count.
- ``turn_count`` payload field is the session-lifetime turn count.
- The hook stores the "last review reading" (lifetime value at the time of the
  last triggered fork).  A fork fires when the delta since the last reading
  reaches the configured interval — i.e. ``current - last_reading >= interval``.
- After a fork the reading is updated to ``current``, so the clock restarts.

Anti-recursion (decision 6):
- ``fork_conversation`` is absent (``None``) inside the forked side-chain because
  the fork is created without a hook_runner that has background hooks.  This
  naturally prevents the fork from triggering another fork.
"""

from __future__ import annotations

import logging
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Review prompt constants (from hermes-agent reference §3)
# ---------------------------------------------------------------------------

_SKILL_REVIEW_PROMPT = (
    "You are in a background self-improvement session.\n\n"
    "Review the skills you have accumulated so far. "
    "Identify any that are redundant, outdated, or could be improved. "
    "Use the skill_manage tool to create new skills, update existing ones, "
    "or delete skills that are no longer useful. "
    "Focus on skills that would make you more effective for the user's typical tasks.\n\n"
    "Be concise and only act when you see a clear improvement opportunity."
)

_MEMORY_REVIEW_PROMPT = (
    "You are in a background self-improvement session.\n\n"
    "Review your memory notes. "
    "Identify facts, preferences, or context that should be updated, "
    "consolidated, or removed because they are stale or redundant. "
    "Use the memory tool to make targeted updates.\n\n"
    "Be conservative — only update entries when the change clearly improves accuracy."
)

_COMBINED_REVIEW_PROMPT = (
    "You are in a background self-improvement session.\n\n"
    "Review both your memory notes and your accumulated skills.\n\n"
    "For memory: identify facts or context that should be updated, consolidated, "
    "or removed because they are stale or redundant.\n\n"
    "For skills: identify any that are redundant, outdated, or could be improved. "
    "Create, update, or delete skills where you see a clear improvement.\n\n"
    "Use the memory and skill_manage tools as needed. "
    "Be concise and only act when you see a clear improvement opportunity."
)


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------


def setup(hooks: Any) -> None:  # noqa: ANN001
    """Register the background self-improvement hook on agent_end.

    Args:
        hooks: HookAPI object providing ``.on()`` and ``.set_state()`` methods.

    Notes:
        Closure state is keyed by ``session_id`` so a single hook registration
        correctly handles multiple concurrent sessions.
    """

    state_lock = Lock()
    # Per-session: {"last_skill_iter": int, "last_memory_turn": int}
    session_state: dict[str, dict[str, int]] = {}

    async def on_agent_end(payload: dict[str, Any], ctx: Any) -> None:  # noqa: ANN001
        """Fire a self-evolution review fork when the nudge counter threshold is reached.

        Args:
            payload: agent_end event payload with ``tool_iterations`` and ``turn_count``.
            ctx: HookContext; provides ``fork_conversation``, ``metadata``,
                ``session_id``, and ``publish_session_event``.
        """
        # Anti-recursion: fork side-chain has no fork_conversation.
        fork_fn = getattr(ctx, "fork_conversation", None)
        if fork_fn is None:
            return

        meta = getattr(ctx, "metadata", {}) or {}
        evolution_cfg = meta.get("self_evolution", {})

        if not evolution_cfg.get("enabled", True):
            return

        skill_creation_enabled: bool = evolution_cfg.get("skill_creation", True)
        memory_curation_enabled: bool = evolution_cfg.get("memory_curation", True)
        skill_interval: int = int(evolution_cfg.get("skill_nudge_interval", 10))
        memory_interval: int = int(evolution_cfg.get("memory_nudge_interval", 10))

        current_iters: int = int(payload.get("tool_iterations", 0))
        current_turns: int = int(payload.get("turn_count", 0))

        session_id: str = getattr(ctx, "session_id", "") or ""

        with state_lock:
            state = session_state.setdefault(
                session_id, {"last_skill_iter": 0, "last_memory_turn": 0}
            )
            last_skill = state["last_skill_iter"]
            last_memory = state["last_memory_turn"]

        review_skills = (
            skill_creation_enabled and (current_iters - last_skill) >= skill_interval
        )
        review_memory = (
            memory_curation_enabled and (current_turns - last_memory) >= memory_interval
        )

        if not review_skills and not review_memory:
            return

        # Build prompt and tool allowlist.
        if review_skills and review_memory:
            review_prompt = _COMBINED_REVIEW_PROMPT
            tool_allowlist = ("skill_manage", "memory")
        elif review_memory:
            review_prompt = _MEMORY_REVIEW_PROMPT
            tool_allowlist = ("memory",)
        else:
            review_prompt = _SKILL_REVIEW_PROMPT
            tool_allowlist = ("skill_manage",)

        try:
            fork_result = await fork_fn(
                review_prompt,
                tool_allowlist=tool_allowlist,
                max_turns=16,
            )
        except Exception:
            logger.exception(
                "self_improvement: fork_conversation raised an exception for session %s",
                session_id,
            )
            return

        # Update per-session readings only after a successful fork.
        with state_lock:
            state = session_state.setdefault(
                session_id, {"last_skill_iter": 0, "last_memory_turn": 0}
            )
            if review_skills:
                state["last_skill_iter"] = current_iters
            if review_memory:
                state["last_memory_turn"] = current_turns

        # Emit session event so CLI / IM can surface a notification.
        publish = getattr(ctx, "publish_session_event", None)
        if callable(publish):
            tool_names_called = getattr(fork_result, "tool_names_called", ()) or ()
            publish(
                event="self_evolution_review",
                data={
                    "session_id": session_id,
                    "reviewed_skills": review_skills,
                    "reviewed_memory": review_memory,
                    "tool_names_called": list(tool_names_called),
                    "completed": getattr(fork_result, "completed", False),
                },
            )

    hooks.on(
        "agent_end",
        on_agent_end,
        priority=200,
        timeout_ms=0,
        mode="background",
    )
