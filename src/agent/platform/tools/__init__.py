"""Platform-owned tool implementations: builtins, loader, and safety."""

from importlib import import_module
from typing import Any

__all__ = ["builtins"]


def __getattr__(name: str) -> Any:
    """Resolve platform tool subpackages lazily for import-cycle safety."""
    if name == "builtins":
        return import_module("agent.platform.tools.builtins")
    raise AttributeError(name)


def __dir__() -> list[str]:
    """Return stable platform tool exports for interactive inspection."""
    return sorted(__all__)
