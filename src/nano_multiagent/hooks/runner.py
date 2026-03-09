"""Compatibility shim re-exporting the canonical core hook runner."""

from nano_multiagent.core.hooks.runner import HookExecution, HookRunner, InterceptDispatchResult

__all__ = ["HookExecution", "HookRunner", "InterceptDispatchResult"]
