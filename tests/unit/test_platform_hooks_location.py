"""Verify platform/hooks is the canonical home for loader and builtins."""

import nano_multiagent.hooks.builtins as legacy_builtins
import nano_multiagent.platform.hooks.builtins as platform_builtins
from nano_multiagent.hooks.session_events import get_session_event_publisher as legacy_get_session_event_publisher
from nano_multiagent.hooks.session_events import set_session_event_publisher_factory as legacy_set_session_event_publisher_factory
from nano_multiagent.hooks.session_usage import SessionUsageSnapshot as LegacySessionUsageSnapshot
from nano_multiagent.hooks.session_usage import get_session_usage_snapshot as legacy_get_session_usage_snapshot
from nano_multiagent.hooks.session_usage import set_session_usage_snapshot_reader as legacy_set_session_usage_snapshot_reader
from nano_multiagent.hooks.loader import build_hook_registry as legacy_build_hook_registry
from nano_multiagent.hooks.loader import discover_hook_files as legacy_discover_hook_files
from nano_multiagent.hooks.loader import (
    load_hooks_from_directories as legacy_load_hooks_from_directories,
)
from nano_multiagent.platform.hooks.loader import build_hook_registry
from nano_multiagent.platform.hooks.loader import discover_hook_files
from nano_multiagent.platform.hooks.loader import load_hooks_from_directories
from nano_multiagent.platform.hooks.session_events import get_session_event_publisher, set_session_event_publisher_factory
from nano_multiagent.platform.hooks.session_usage import SessionUsageSnapshot, get_session_usage_snapshot, set_session_usage_snapshot_reader


def test_platform_hooks_loader_is_canonical_home() -> None:
    """Platform hook loader functions must originate from platform modules."""
    assert build_hook_registry.__module__ == "nano_multiagent.platform.hooks.loader"
    assert discover_hook_files.__module__ == "nano_multiagent.platform.hooks.loader"
    assert load_hooks_from_directories.__module__ == "nano_multiagent.platform.hooks.loader"


def test_platform_hooks_builtins_is_canonical_home() -> None:
    """Platform hook builtins package must live under the platform path."""
    assert platform_builtins.__name__ == "nano_multiagent.platform.hooks.builtins"


def test_platform_hook_session_contracts_are_canonical_home() -> None:
    """Platform hook session contracts must originate from platform modules."""
    assert SessionUsageSnapshot.__module__ == "nano_multiagent.platform.hooks.session_usage"
    assert get_session_usage_snapshot.__module__ == "nano_multiagent.platform.hooks.session_usage"
    assert set_session_usage_snapshot_reader.__module__ == "nano_multiagent.platform.hooks.session_usage"
    assert get_session_event_publisher.__module__ == "nano_multiagent.platform.hooks.session_events"
    assert set_session_event_publisher_factory.__module__ == "nano_multiagent.platform.hooks.session_events"


def test_old_hooks_paths_are_compat_shims() -> None:
    """Legacy hook modules must re-export the canonical platform objects."""
    assert legacy_build_hook_registry is build_hook_registry
    assert legacy_discover_hook_files is discover_hook_files
    assert legacy_load_hooks_from_directories is load_hooks_from_directories
    assert legacy_builtins is platform_builtins
    assert LegacySessionUsageSnapshot is SessionUsageSnapshot
    assert legacy_get_session_usage_snapshot is get_session_usage_snapshot
    assert legacy_set_session_usage_snapshot_reader is set_session_usage_snapshot_reader
    assert legacy_get_session_event_publisher is get_session_event_publisher
    assert legacy_set_session_event_publisher_factory is set_session_event_publisher_factory
