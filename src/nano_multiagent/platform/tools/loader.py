"""Shim: platform/tools/loader re-exports from canonical tools.loader.

Canonical location: nano_multiagent.tools.loader
New platform alias: nano_multiagent.platform.tools.loader
"""

from nano_multiagent.tools.loader import (  # noqa: F401
    build_tool_registry,
    discover_tool_files,
    load_tools_from_directory,
)

__all__ = [
    "build_tool_registry",
    "discover_tool_files",
    "load_tools_from_directory",
]
