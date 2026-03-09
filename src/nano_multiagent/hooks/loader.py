"""Compatibility shim for the canonical platform hook loader."""

from nano_multiagent.platform.hooks.loader import (  # noqa: F401
    build_hook_registry,
    discover_hook_files,
    load_hooks_from_directories,
)

__all__ = [
    "build_hook_registry",
    "discover_hook_files",
    "load_hooks_from_directories",
]
