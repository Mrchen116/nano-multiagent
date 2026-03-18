"""Built-in tool defaults for the personal_assistant product."""

# Conservative defaults per NodeGateway-SPEC.md §12; advanced tools are opt-in via tool_allowlist.
DEFAULT_TOOL_IDS = ["read", "task"]
OPTIONAL_TOOL_IDS = ["send_message"]

__all__ = ["DEFAULT_TOOL_IDS", "OPTIONAL_TOOL_IDS"]
