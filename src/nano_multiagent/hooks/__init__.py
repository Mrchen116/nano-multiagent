"""Hook subsystem: registration, loading, and event dispatch."""

from .context import HookContext, HookLogger
from .loader import build_hook_registry, discover_hook_files, load_hooks_from_directories
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
    "HookRegistration",
    "HookRegistry",
    "HookRunner",
    "InterceptDispatchResult",
    "LoadedHookModule",
    "build_hook_registry",
    "discover_hook_files",
    "event_mode_of",
    "load_hooks_from_directories",
]

