"""Platform shim for built-in tool implementations.

Canonical location: nano_multiagent.tools.builtins
New platform alias: nano_multiagent.platform.tools.builtins
"""

from nano_multiagent.tools.builtins import builtin_tools, register_builtin_tools  # noqa: F401

__all__ = ["builtin_tools", "register_builtin_tools"]
