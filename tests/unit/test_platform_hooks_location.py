"""Verify platform/hooks is the canonical home for loader and builtins."""

from importlib.util import find_spec

import agent.platform.hooks.builtins as platform_builtins
from agent.platform.hooks.loader import build_hook_registry
from agent.platform.hooks.loader import discover_hook_files
from agent.platform.hooks.loader import load_hooks_from_directories
from agent.platform.hooks.session_events import (
    get_session_event_publisher,
    set_session_event_publisher_factory,
)
from agent.platform.hooks.session_usage import (
    SessionUsageSnapshot,
    get_session_usage_snapshot,
    set_session_usage_snapshot_reader,
)


def test_platform_hooks_loader_is_canonical_home() -> None:
    """Platform hook loader functions must originate from platform modules."""
    assert build_hook_registry.__module__ == "agent.platform.hooks.loader"
    assert discover_hook_files.__module__ == "agent.platform.hooks.loader"
    assert load_hooks_from_directories.__module__ == "agent.platform.hooks.loader"


def test_platform_hooks_builtins_is_canonical_home() -> None:
    """Platform hook builtins package must live under the platform path."""
    assert platform_builtins.__name__ == "agent.platform.hooks.builtins"


def test_platform_hook_session_contracts_are_canonical_home() -> None:
    """Platform hook session contracts must originate from platform modules."""
    assert SessionUsageSnapshot.__module__ == "agent.platform.hooks.session_usage"
    assert get_session_usage_snapshot.__module__ == "agent.platform.hooks.session_usage"
    assert (
        set_session_usage_snapshot_reader.__module__
        == "agent.platform.hooks.session_usage"
    )
    assert (
        get_session_event_publisher.__module__ == "agent.platform.hooks.session_events"
    )
    assert (
        set_session_event_publisher_factory.__module__
        == "agent.platform.hooks.session_events"
    )


def test_legacy_hooks_root_is_removed() -> None:
    assert find_spec("agent.hooks") is None
