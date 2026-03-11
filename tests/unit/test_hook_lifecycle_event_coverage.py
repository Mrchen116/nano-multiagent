from agent.core.events import RuntimeEventType


def test_runtime_event_types_cover_lifecycle_and_terminal_events() -> None:
    runtime_events = {event.value for event in RuntimeEventType}
    required = {
        "session_start",
        "session_compact",
        "session_shutdown",
        "run_error",
        "run_timeout",
    }

    assert required <= runtime_events
