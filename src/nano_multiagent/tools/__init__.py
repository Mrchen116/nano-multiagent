"""Tooling subsystem package with lazy top-level exports.

Lazy exports avoid import cycles while the platform layer owns the canonical
loader/safety/builtins implementations.
"""

from importlib import import_module
from typing import Any

__all__ = [
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolSafety",
    "ToolSafetyConfig",
    "build_tool_registry",
    "discover_tool_files",
    "load_tools_from_directory",
]


def __getattr__(name: str) -> Any:
    """Resolve tool package exports lazily for import-cycle safety."""
    if name in {"Tool", "ToolContext"}:
        module = import_module("nano_multiagent.tools.base")
        return getattr(module, name)
    if name == "ToolRegistry":
        return import_module("nano_multiagent.tools.registry").ToolRegistry
    if name in {"ToolSafety", "ToolSafetyConfig"}:
        module = import_module("nano_multiagent.tools.safety")
        return getattr(module, name)
    if name in {"build_tool_registry", "discover_tool_files", "load_tools_from_directory"}:
        module = import_module("nano_multiagent.tools.loader")
        return getattr(module, name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    """Return stable package exports for interactive inspection."""
    return sorted(__all__)
