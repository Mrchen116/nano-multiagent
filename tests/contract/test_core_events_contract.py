from nano_multiagent.core.events import RuntimeEventType


def test_runtime_event_types_are_stable() -> None:
    assert [event.value for event in RuntimeEventType] == [
        "input",
        "before_agent_start",
        "turn_start",
        "message_update",
        "tool_call",
        "tool_result",
        "run_error",
        "run_timeout",
    ]
