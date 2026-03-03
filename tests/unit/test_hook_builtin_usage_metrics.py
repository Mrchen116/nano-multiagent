import asyncio

from nano_multiagent.hooks.builtins import usage_metrics
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.hooks.registry import HookAPI, HookRegistry
from nano_multiagent.hooks.runner import HookRunner
from nano_multiagent.hooks.usage_metrics_registry import (
    clear_session_usage_reader,
    get_session_usage_snapshot,
)


def _build_registry_with_usage_hook() -> HookRegistry:
    registry = HookRegistry()
    usage_metrics.setup(
        HookAPI(
            registry,
            source="builtin",
            module_name="tests.unit.usage_metrics",
            file_path=None,
        )
    )
    return registry


def test_builtin_usage_metrics_hook_accumulates_and_deduplicates_turn_usage() -> None:
    clear_session_usage_reader()
    registry = _build_registry_with_usage_hook()
    runner = HookRunner(registry=registry)

    asyncio.run(
        runner.dispatch_observe(
            "turn_end",
            {
                "session_id": "sess_usage_1",
                "turn_id": "turn_1",
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            },
            HookContext(session_id="sess_usage_1", turn_id="turn_1"),
        )
    )
    asyncio.run(
        runner.dispatch_observe(
            "turn_end",
            {
                "session_id": "sess_usage_1",
                "turn_id": "turn_1",
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            },
            HookContext(session_id="sess_usage_1", turn_id="turn_1"),
        )
    )
    asyncio.run(
        runner.dispatch_observe(
            "turn_end",
            {
                "session_id": "sess_usage_1",
                "turn_id": "turn_2",
                "usage": {"prompt_tokens": 90, "completion_tokens": 10, "total_tokens": 100},
            },
            HookContext(session_id="sess_usage_1", turn_id="turn_2"),
        )
    )

    snapshot = get_session_usage_snapshot("sess_usage_1")
    assert snapshot is not None
    assert snapshot.prompt_tokens == 190
    assert snapshot.completion_tokens == 30
    assert snapshot.total_tokens == 220
    assert snapshot.last_prompt_tokens == 90
    assert snapshot.last_completion_tokens == 10
    assert snapshot.last_total_tokens == 100
    assert snapshot.turn_count == 2

    clear_session_usage_reader()


def test_builtin_usage_metrics_hook_cleans_session_state_on_shutdown() -> None:
    clear_session_usage_reader()
    registry = _build_registry_with_usage_hook()
    runner = HookRunner(registry=registry)

    asyncio.run(
        runner.dispatch_observe(
            "turn_end",
            {
                "session_id": "sess_usage_2",
                "turn_id": "turn_1",
                "usage": {"prompt_tokens": 50, "completion_tokens": 5, "total_tokens": 55},
            },
            HookContext(session_id="sess_usage_2", turn_id="turn_1"),
        )
    )
    assert get_session_usage_snapshot("sess_usage_2") is not None

    asyncio.run(
        runner.dispatch_observe(
            "session_shutdown",
            {"session_id": "sess_usage_2"},
            HookContext(session_id="sess_usage_2"),
        )
    )
    assert get_session_usage_snapshot("sess_usage_2") is None

    clear_session_usage_reader()
