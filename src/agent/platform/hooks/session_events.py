"""Per-hook-registry session event publishing contract."""

from __future__ import annotations

from typing import Callable, Mapping

from agent.core.hooks.registry import HookRegistry

SessionEventPublisher = Callable[[str, Mapping[str, object]], None]
SessionEventPublisherFactory = Callable[[str], SessionEventPublisher | None]

SESSION_EVENT_PUBLISHER_FACTORY_STATE_KEY = "session_event_publisher_factory"


def set_session_event_publisher_factory(
    *,
    registry: HookRegistry,
    factory: SessionEventPublisherFactory | None,
) -> None:
    """Register or clear one session event publisher factory on hook registry."""

    registry.set_extension_state(SESSION_EVENT_PUBLISHER_FACTORY_STATE_KEY, factory)


def get_session_event_publisher(
    *,
    registry: HookRegistry,
    session_id: str,
) -> SessionEventPublisher | None:
    """Resolve one session-scoped event publisher from hook registry state."""

    factory = registry.get_extension_state(SESSION_EVENT_PUBLISHER_FACTORY_STATE_KEY)
    if not callable(factory):
        return None
    publisher = factory(session_id)
    if not callable(publisher):
        return None
    return publisher
