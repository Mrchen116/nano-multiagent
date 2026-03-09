"""Compatibility shim for the canonical platform tool safety module."""

from nano_multiagent.platform.tools.safety import (  # noqa: F401
    CommandExecution,
    CommandPolicyDecision,
    ToolSafety,
    ToolSafetyConfig,
    load_tool_safety_config,
)

__all__ = [
    "CommandExecution",
    "CommandPolicyDecision",
    "ToolSafety",
    "ToolSafetyConfig",
    "load_tool_safety_config",
]
