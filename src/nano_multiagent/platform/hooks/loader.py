"""Shim: platform/hooks/loader re-exports from canonical hooks.loader.

Canonical location: nano_multiagent.hooks.loader
New platform alias: nano_multiagent.platform.hooks.loader
"""

from nano_multiagent.hooks.loader import (  # noqa: F401
    build_hook_registry,
    discover_hook_files,
    load_hooks_from_directories,
)

__all__ = [
    "build_hook_registry",
    "discover_hook_files",
    "load_hooks_from_directories",
]
