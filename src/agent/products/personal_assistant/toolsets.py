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
    # cron is opt-in per agent: only reaches a session when that agent's cron_enabled
    # flag materialises it into the tool_allowlist at session-creation time.
    "cron",
]

__all__ = ["DEFAULT_TOOL_IDS", "OPTIONAL_TOOL_IDS"]
