"""Shim: platform/tools/safety re-exports from canonical tools.safety.

Canonical location: nano_multiagent.tools.safety
New platform alias: nano_multiagent.platform.tools.safety
"""

from nano_multiagent.tools.safety import (  # noqa: F401
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
