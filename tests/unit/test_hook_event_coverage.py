from nano_multiagent.core.events import RuntimeEventType
from nano_multiagent.core.hooks.types import ALL_HOOK_EVENTS


def test_runtime_event_types_cover_run_terminal_hook_events() -> None:
    runtime_events = {event.value for event in RuntimeEventType}
    required = {"run_error", "run_timeout", "run_abort"}

    assert required <= set(ALL_HOOK_EVENTS)
    assert required <= runtime_events
