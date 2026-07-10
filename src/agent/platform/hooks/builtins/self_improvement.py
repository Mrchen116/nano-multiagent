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

# Review prompts — faithful port of hermes background_review.py §3, adapted to
# our tool vocabulary: skill_manage action=list/write_file/patch/edit/create and
# skill_view for reading SKILL.md content.
# All skill inspection + change goes through skill tools; general file tools
# (read/bash) are not in the review fork's execution allowlist.

_MEMORY_REVIEW_PROMPT = (
    "Review the conversation above and consider saving to memory if appropriate.\n\n"
    "Focus on:\n"
    "1. Has the user revealed things about themselves — their persona, desires, "
    "preferences, or personal details worth remembering?\n"
    "2. Has the user expressed expectations about how you should behave, their work "
    "style, or ways they want you to operate?\n\n"
    "If something stands out, save it using the memory tool, and include a short "
    "source index (which turn / what was said) on each entry so it can be traced. "
    "If nothing is worth saving, just say 'Nothing to save.' and stop."
)

_SKILL_REVIEW_PROMPT = (
    "Review the conversation above and update the skill library. Be ACTIVE — most "
    "sessions produce at least one skill update, even if small. A pass that does "
    "nothing is a missed learning opportunity, not a neutral outcome.\n\n"
    "Use skill_manage action=list to see skills, skill_view to read one, "
    "skill_manage action=patch/edit/create to change SKILL.md, and skill_manage "
    "action=write_file to add a support file. (General file tools are not available "
    "in this session.)\n\n"
    "Target shape of the library: CLASS-LEVEL skills, each with a rich SKILL.md and "
    "support files for session-specific detail. Not a long flat list of narrow "
    "one-session-one-skill entries. This shapes HOW you update, not WHETHER you update.\n\n"
    "Signals to look for (any one warrants action):\n"
    "  • User corrected your style, tone, format, or verbosity. Frustration signals "
    "('stop doing X', 'too verbose', 'just give me the answer', 'you always do Y and "
    "I hate it') and explicit 'remember this' are FIRST-CLASS skill signals, not just "
    "memory signals — embed the preference in the relevant skill so the next session "
    "starts already knowing.\n"
    "  • User corrected your workflow or sequence of steps — encode it as a pitfall or "
    "explicit step in the skill that governs that class of task.\n"
    "  • A non-trivial technique, fix, workaround, or tool-usage pattern emerged.\n"
    "  • A skill consulted this session turned out wrong, missing a step, or outdated — "
    "patch it NOW.\n\n"
    "Preference order — pick the earliest that fits, but do pick one when a signal fired:\n"
    "  1. UPDATE A SKILL THAT WAS IN PLAY. Look back for skills you viewed/used this "
    "session (skill_view); if one covers the new learning, patch it first.\n"
    "  2. UPDATE AN EXISTING UMBRELLA (skill_manage action=list + skill_view to find "
    "the right one); add a subsection, a pitfall, or broaden a trigger.\n"
    "  3. ADD A SUPPORT FILE under an existing umbrella via skill_manage "
    "action=write_file, file_path starting 'references/' (session detail / condensed "
    "knowledge banks: error transcripts, repro recipes, API/doc excerpts, domain notes "
    "— concise, task-focused, not a full mirror of upstream docs), 'templates/' "
    "(copy-and-modify starters), or 'scripts/' (re-runnable verification/probe actions). "
    "Add a one-line pointer in the umbrella's SKILL.md so future sessions know it exists.\n"
    "  4. CREATE A NEW CLASS-LEVEL UMBRELLA when no existing skill covers the class. "
    "The name MUST be class-level — NOT a PR number, error string, feature codename, "
    "library-alone name, or 'fix-X / debug-Y' session artifact. If the name only makes "
    "sense for today's task, fall back to (1)/(2)/(3).\n\n"
    "User-preference embedding: when the user complains about how you handled a task, "
    "the lesson belongs in the SKILL.md that governs that task, not just memory. Memory "
    "captures 'who the user is'; skills capture 'how to do this class of task'.\n\n"
    "Do NOT capture as skills (these harden into self-imposed constraints that bite "
    "later when the environment changes):\n"
    "  • Environment-dependent failures: missing binaries, fresh-install errors, "
    "'command not found', unconfigured credentials, uninstalled packages — the user "
    "can fix these; they are not durable rules.\n"
    "  • Negative claims about tools/features ('X tool is broken', 'cannot use Y') — "
    "they become refusals the agent cites against itself long after the fix.\n"
    "  • Transient errors that resolved before the conversation ended — if a retry "
    "worked, the lesson is the retry pattern, not the original failure.\n"
    "  • One-off task narratives ('summarize today's market', 'analyze this PR').\n\n"
    "If a tool failed because of setup state, capture the FIX (install command, config "
    "step, env var) under a setup/troubleshooting skill — never 'this tool does not work' "
    "as a standalone constraint.\n\n"
    "'Nothing to save.' is a real option but should NOT be the default. If the session "
    "ran smoothly with no corrections and produced no new technique, say 'Nothing to "
    "save.' and stop. Otherwise, act."
)

_COMBINED_REVIEW_PROMPT = (
    "Review the conversation above and update two things.\n\n"
    "**Memory** — who the user is: did the user reveal persona, desires, preferences, "
    "personal details, or expectations about how you should behave? Save durable facts "
    "with the memory tool, each with a short source index (which turn / what was said).\n\n"
    "**Skills** — how to do this class of task. Be ACTIVE: most sessions produce at "
    "least one skill update; a pass that does nothing is a missed learning opportunity. "
    "Use skill_manage action=list/write_file/patch/edit/create for skill changes and "
    "skill_view for reading SKILL.md content; general file tools are unavailable here.\n\n"
    "Target shape: CLASS-LEVEL skills with a rich SKILL.md and support files for "
    "session-specific detail — not a flat list of narrow one-session entries.\n\n"
    "Signals that warrant a skill update (any one is enough): user corrected your "
    "style/tone/format/verbosity/workflow (frustration is a FIRST-CLASS skill signal, "
    "not just memory — embed it in the governing skill); a non-trivial technique/fix "
    "emerged; a consulted skill turned out wrong/outdated (patch now).\n\n"
    "Preference order for skills — earliest that fits:\n"
    "  1. PATCH A SKILL THAT WAS IN PLAY (skill_view to re-read it).\n"
    "  2. UPDATE AN EXISTING UMBRELLA (skill_manage action=list + skill_view to find it).\n"
    "  3. ADD A SUPPORT FILE via skill_manage action=write_file — file_path under "
    "'references/' (session detail / condensed knowledge banks), 'templates/' "
    "(copy-and-modify starters), or 'scripts/' (re-runnable actions); add a one-line "
    "pointer in SKILL.md.\n"
    "  4. CREATE A NEW CLASS-LEVEL UMBRELLA when nothing exists — name at the class "
    "level, NOT a PR number, error string, codename, or 'fix-X / debug-Y' artifact.\n\n"
    "User-preference embedding: when the user complains about how you handled a task, "
    "update the skill that governs it — memory alone isn't enough.\n\n"
    "Do NOT capture as skills: environment-dependent failures (missing binaries, "
    "'command not found', unconfigured credentials); negative claims about tools "
    "('X is broken'); transient errors that already resolved (capture the retry/fix, "
    "not the failure); one-off task narratives.\n\n"
    "'Nothing to save.' is a real option but should NOT be the default — act unless the "
    "session ran smoothly with no corrections and no new technique."
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
            tool_allowlist = ("skill_manage", "skill_view", "memory")
        elif review_memory:
            review_prompt = _MEMORY_REVIEW_PROMPT
            tool_allowlist = ("memory",)
        else:
            review_prompt = _SKILL_REVIEW_PROMPT
            tool_allowlist = ("skill_manage", "skill_view")

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

    # timeout_ms is not enforced for BACKGROUND mode (fire-and-forget), but the
    # registry requires a positive value for all registrations; use a nominal
    # value that would be ignored in practice.
    hooks.on(
        "agent_end",
        on_agent_end,
        priority=200,
        timeout_ms=1500,
        mode="background",
    )
