"""Hook module exports for the personal_assistant product."""

from __future__ import annotations

from typing import Any

# auto_mode_gate added in feat-333 (unified allow/deny/ask classifier).
# self_improvement added in feat-349-M3: background self-evolution hook.
# communication_context removed from hooks in feat-379-M1: the
# [Communication Context] block is now assembled by the pa.communication_context
# segment (prompt_sections.py) — no hook registration needed.
DEFAULT_HOOK_MODULES = [
    "auto_mode_gate",
    "default_status",
    "usage_metrics",
    "chat_history",
    "realtime_stream",
    "self_improvement",
]


def setup(hooks: Any) -> None:  # noqa: ANN401
    # feat-379-M1: communication_context hook retired; no before_agent_start
    # registration.  The pa.communication_context segment (order=900) in
    # prompt_sections.py handles group-chat context injection instead.
    pass


__all__ = ["DEFAULT_HOOK_MODULES", "setup"]
