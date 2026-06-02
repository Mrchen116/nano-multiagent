"""Built-in tool defaults for the personal_assistant product."""

# skill_manage and memory added in feat-349-M3: self-evolution wiring.
DEFAULT_TOOL_IDS = [
    "read",
    "write",
    "edit",
    "bash",
    "agent",
    "task_stop",
    "web_fetch",
    "web_search",
    "skill_manage",
    "memory",
]
OPTIONAL_TOOL_IDS = [
    "send_message",
    # feat-394 decision 7: cron is PA-only; coding_cli must not include this.
    # Gated by cron_enabled per-agent flag (injected via tool_allowlist at session creation time).
    "cron",
]

__all__ = ["DEFAULT_TOOL_IDS", "OPTIONAL_TOOL_IDS"]
