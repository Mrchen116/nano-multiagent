"""Canonical shared hook abstractions and execution contracts."""

from .context import HookContext, HookLogger, HookModelCall, HookModelResult
from .registry import HookAPI, HookRegistry
from .runner import HookExecution, HookRunner, InterceptDispatchResult
from .types import (
    ALL_HOOK_EVENTS,
    INTERCEPT_EVENTS,
    OBSERVE_EVENTS,
    DEFAULT_HOOK_PRIORITY,
    DEFAULT_HOOK_TIMEOUT_MS,
    HookEventMode,
    HookEventType,
    HookRegistration,
    LoadedHookModule,
    event_mode_of,
    normalize_hook_event,
)

__all__ = [
    "ALL_HOOK_EVENTS",
    "INTERCEPT_EVENTS",
    "OBSERVE_EVENTS",
    "DEFAULT_HOOK_PRIORITY",
    "DEFAULT_HOOK_TIMEOUT_MS",
    "HookAPI",
    "HookContext",
    "HookEventMode",
    "HookEventType",
    "HookExecution",
    "HookLogger",
    "HookModelCall",
    "HookModelResult",
    "HookRegistration",
    "HookRegistry",
    "HookRunner",
    "InterceptDispatchResult",
    "LoadedHookModule",
    "event_mode_of",
    "normalize_hook_event",
]
