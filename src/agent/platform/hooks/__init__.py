"""Platform-owned hook implementations: builtins and loader."""

from importlib import import_module
from typing import Any

__all__ = ["builtins"]


def __getattr__(name: str) -> Any:
    """Resolve platform hook subpackages lazily for import-cycle safety."""
    if name == "builtins":
        return import_module("agent.platform.hooks.builtins")
    raise AttributeError(name)


def __dir__() -> list[str]:
    """Return stable platform hook exports for interactive inspection."""
    return sorted(__all__)
