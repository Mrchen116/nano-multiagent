from agent.core.hooks.types import (
    ALL_HOOK_EVENTS,
    INTERCEPT_EVENTS,
    OBSERVE_EVENTS,
    DEFAULT_HOOK_PRIORITY,
    DEFAULT_HOOK_TIMEOUT_MS,
    HookEventType,
)


def test_hook_event_contracts_are_stable() -> None:
    assert HookEventType.INPUT.value == "input"
    assert HookEventType.TOOL_CALL.value == "tool_call"
    assert HookEventType.TOOL_RESULT.value == "tool_result"
    assert DEFAULT_HOOK_PRIORITY == 100
    assert DEFAULT_HOOK_TIMEOUT_MS == 1500

    assert {"input", "before_agent_start", "tool_call", "tool_result"} == set(INTERCEPT_EVENTS)
    assert "turn_start" in OBSERVE_EVENTS
    assert "run_error" in OBSERVE_EVENTS

    assert set(ALL_HOOK_EVENTS) == set(INTERCEPT_EVENTS | OBSERVE_EVENTS)

