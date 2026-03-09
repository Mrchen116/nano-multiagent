"""Compatibility shim for the canonical platform tool loader."""

from nano_multiagent.platform.tools.loader import (  # noqa: F401
    build_tool_registry,
    discover_tool_files,
    load_tools_from_directory,
)

__all__ = [
    "build_tool_registry",
    "discover_tool_files",
    "load_tools_from_directory",
]
