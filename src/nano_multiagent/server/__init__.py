"""Compatibility shim package for the canonical platform HTTP API.

Only the package root and ``server.app`` entrypoint survive in M87 as minimal
external-compat surface; deeper legacy route/helper modules are intentionally
removed.
"""

from importlib import import_module
from typing import Any

__all__ = ["app", "create_app"]


def __getattr__(name: str) -> Any:
    """Resolve legacy server exports lazily for import-cycle safety."""
    if name in {"app", "create_app"}:
        module = import_module("nano_multiagent.platform.http_api")
        return getattr(module, name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    """Return stable legacy server exports for interactive inspection."""
    return sorted(__all__)
