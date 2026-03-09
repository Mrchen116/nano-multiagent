"""Compatibility shim re-exporting canonical core hook context types."""

from nano_multiagent.core.hooks.context import (
    HookContext,
    HookLogger,
    HookModelCall,
    HookModelCaller,
    HookModelResult,
    HookSessionEventPublisher,
    LogSink,
)

__all__ = [
    "HookContext",
    "HookLogger",
    "HookModelCall",
    "HookModelCaller",
    "HookModelResult",
    "HookSessionEventPublisher",
    "LogSink",
]
