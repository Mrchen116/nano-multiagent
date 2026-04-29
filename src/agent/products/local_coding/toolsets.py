"""Built-in tool defaults for the local_coding product."""

DEFAULT_TOOL_IDS = ["read", "write", "edit", "bash", "agent", "task_stop"]
OPTIONAL_TOOL_IDS: list[str] = []

__all__ = ["DEFAULT_TOOL_IDS", "OPTIONAL_TOOL_IDS"]
