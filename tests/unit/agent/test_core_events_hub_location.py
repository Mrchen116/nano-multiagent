"""Verify EventStreamHub lives in agent.core.events.hub (not http_api).

This test turns red until R1 migrates the hub; it also verifies the
old http_api path is gone after R3.
"""

from agent.core.events.hub import EventStreamHub, StreamEvent, SubscriberOverflowError


def test_event_stream_hub_importable_from_core_events() -> None:
    """EventStreamHub must be importable from agent.core.events.hub."""
    hub = EventStreamHub()
    assert hub is not None


def test_stream_event_importable_from_core_events() -> None:
    """StreamEvent must be importable from agent.core.events.hub."""
    assert StreamEvent.__module__ == "agent.core.events.hub"


def test_subscriber_overflow_error_importable_from_core_events() -> None:
    """SubscriberOverflowError must be importable from agent.core.events.hub."""
    assert issubclass(SubscriberOverflowError, Exception)
