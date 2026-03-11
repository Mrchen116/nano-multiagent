"""Verify core/hooks is the canonical home for shared hook abstractions."""

from agent.core.hooks import (
    ALL_HOOK_EVENTS,
    DEFAULT_HOOK_PRIORITY,
    DEFAULT_HOOK_TIMEOUT_MS,
    HookAPI,
    HookContext,
    HookEventMode,
    HookEventType,
    HookExecution,
    HookLogger,
    HookModelCall,
    HookModelResult,
    HookRegistration,
    HookRegistry,
    HookRunner,
    InterceptDispatchResult,
    LoadedHookModule,
    event_mode_of,
)
from agent.core.hooks.context import HookContext as CoreHookContext
from agent.core.hooks.context import HookLogger as CoreHookLogger
from agent.core.hooks.context import HookModelCall as CoreHookModelCall
from agent.core.hooks.context import HookModelResult as CoreHookModelResult
from agent.core.hooks.registry import HookAPI as CoreHookAPI
from agent.core.hooks.registry import HookRegistry as CoreHookRegistry
from agent.core.hooks.runner import HookExecution as CoreHookExecution
from agent.core.hooks.runner import HookRunner as CoreHookRunner
from agent.core.hooks.runner import InterceptDispatchResult as CoreInterceptDispatchResult
from agent.core.hooks.types import ALL_HOOK_EVENTS as CoreAllHookEvents
from agent.core.hooks.types import DEFAULT_HOOK_PRIORITY as CoreDefaultHookPriority
from agent.core.hooks.types import DEFAULT_HOOK_TIMEOUT_MS as CoreDefaultHookTimeoutMs
from agent.core.hooks.types import HookEventMode as CoreHookEventMode
from agent.core.hooks.types import HookEventType as CoreHookEventType
from agent.core.hooks.types import HookRegistration as CoreHookRegistration
from agent.core.hooks.types import LoadedHookModule as CoreLoadedHookModule
from agent.core.hooks.types import event_mode_of as CoreEventModeOf
from agent.core.hooks.context import HookContext as LegacyHookContext
from agent.core.hooks.context import HookLogger as LegacyHookLogger
from agent.core.hooks.context import HookModelCall as LegacyHookModelCall
from agent.core.hooks.context import HookModelResult as LegacyHookModelResult
from agent.core.hooks.registry import HookAPI as LegacyHookAPI
from agent.core.hooks.registry import HookRegistry as LegacyHookRegistry
from agent.core.hooks.runner import HookExecution as LegacyHookExecution
from agent.core.hooks.runner import HookRunner as LegacyHookRunner
from agent.core.hooks.runner import InterceptDispatchResult as LegacyInterceptDispatchResult
from agent.core.hooks.types import ALL_HOOK_EVENTS as LegacyAllHookEvents
from agent.core.hooks.types import DEFAULT_HOOK_PRIORITY as LegacyDefaultHookPriority
from agent.core.hooks.types import DEFAULT_HOOK_TIMEOUT_MS as LegacyDefaultHookTimeoutMs
from agent.core.hooks.types import HookEventMode as LegacyHookEventMode
from agent.core.hooks.types import HookEventType as LegacyHookEventType
from agent.core.hooks.types import HookRegistration as LegacyHookRegistration
from agent.core.hooks.types import LoadedHookModule as LegacyLoadedHookModule
from agent.core.hooks.types import event_mode_of as LegacyEventModeOf


def test_core_hooks_is_canonical_home() -> None:
    """Core hook exports must originate from core-owned modules."""
    assert HookContext is CoreHookContext
    assert HookLogger is CoreHookLogger
    assert HookModelCall is CoreHookModelCall
    assert HookModelResult is CoreHookModelResult
    assert HookAPI is CoreHookAPI
    assert HookRegistry is CoreHookRegistry
    assert HookExecution is CoreHookExecution
    assert HookRunner is CoreHookRunner
    assert InterceptDispatchResult is CoreInterceptDispatchResult
    assert HookEventType is CoreHookEventType
    assert HookEventMode is CoreHookEventMode
    assert HookRegistration is CoreHookRegistration
    assert LoadedHookModule is CoreLoadedHookModule
    assert DEFAULT_HOOK_PRIORITY == CoreDefaultHookPriority
    assert DEFAULT_HOOK_TIMEOUT_MS == CoreDefaultHookTimeoutMs
    assert ALL_HOOK_EVENTS is CoreAllHookEvents
    assert event_mode_of is CoreEventModeOf

    assert HookContext.__module__ == "agent.core.hooks.context"
    assert HookRegistry.__module__ == "agent.core.hooks.registry"
    assert HookRunner.__module__ == "agent.core.hooks.runner"
    assert HookEventType.__module__ == "agent.core.hooks.types"
    assert HookRegistration.__module__ == "agent.core.hooks.types"


def test_old_hooks_paths_are_compat_shims() -> None:
    """Legacy hook modules must re-export the canonical core hook objects."""
    assert LegacyHookContext is CoreHookContext
    assert LegacyHookLogger is CoreHookLogger
    assert LegacyHookModelCall is CoreHookModelCall
    assert LegacyHookModelResult is CoreHookModelResult
    assert LegacyHookAPI is CoreHookAPI
    assert LegacyHookRegistry is CoreHookRegistry
    assert LegacyHookExecution is CoreHookExecution
    assert LegacyHookRunner is CoreHookRunner
    assert LegacyInterceptDispatchResult is CoreInterceptDispatchResult
    assert LegacyHookEventType is CoreHookEventType
    assert LegacyHookEventMode is CoreHookEventMode
    assert LegacyHookRegistration is CoreHookRegistration
    assert LegacyLoadedHookModule is CoreLoadedHookModule
    assert LegacyDefaultHookPriority == CoreDefaultHookPriority
    assert LegacyDefaultHookTimeoutMs == CoreDefaultHookTimeoutMs
    assert LegacyAllHookEvents is CoreAllHookEvents
    assert LegacyEventModeOf is CoreEventModeOf
