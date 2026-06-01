"""Built-in tool defaults for the local_coding product."""

# skill_manage and memory added in feat-349-M3: self-evolution wiring.
DEFAULT_TOOL_IDS = [
    "read",
    "write",
    "edit",
    "bash",
    "agent",
    "task_stop",
    "skill_manage",
    "memory",
]
OPTIONAL_TOOL_IDS: list[str] = []

__all__ = ["DEFAULT_TOOL_IDS", "OPTIONAL_TOOL_IDS"]
