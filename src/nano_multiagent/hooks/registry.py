"""Compatibility shim re-exporting the canonical core hook registry."""

from nano_multiagent.core.hooks.registry import HookAPI, HookRegistry

__all__ = ["HookAPI", "HookRegistry"]
