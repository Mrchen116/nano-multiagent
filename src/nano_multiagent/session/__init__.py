"""Session domain package.

Exports are resolved lazily so lower-level session submodules can be imported
without triggering manager/service wiring during package initialization.
"""

from importlib import import_module
from typing import Any

__all__ = ["SessionManager", "SessionService"]


def __getattr__(name: str) -> Any:
    """Resolve top-level session exports lazily for import-cycle safety."""
    if name == "SessionManager":
        return import_module("nano_multiagent.session.manager").SessionManager
    if name == "SessionService":
        return import_module("nano_multiagent.session.service").SessionService
    raise AttributeError(name)


def __dir__() -> list[str]:
    """Return stable package exports for interactive inspection."""
    return sorted(__all__)
