"""Compatibility shim for canonical platform session event contracts."""

from nano_multiagent.platform.hooks.session_events import (
    SESSION_EVENT_PUBLISHER_FACTORY_STATE_KEY,
    SessionEventPublisher,
    SessionEventPublisherFactory,
    get_session_event_publisher,
    set_session_event_publisher_factory,
)

__all__ = [
    "SESSION_EVENT_PUBLISHER_FACTORY_STATE_KEY",
    "SessionEventPublisher",
    "SessionEventPublisherFactory",
    "get_session_event_publisher",
    "set_session_event_publisher_factory",
]
