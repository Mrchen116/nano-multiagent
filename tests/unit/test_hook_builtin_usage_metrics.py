import asyncio

from nano_multiagent.hooks.builtins import usage_metrics
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.hooks.registry import HookAPI, HookRegistry
from nano_multiagent.hooks.runner import HookRunner
from nano_multiagent.hooks.session_usage import get_session_usage_snapshot


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

    snapshot = get_session_usage_snapshot(registry=registry, session_id="sess_usage_1")
    assert snapshot is not None
    assert snapshot.prompt_tokens == 190
    assert snapshot.completion_tokens == 30
    assert snapshot.total_tokens == 220
    assert snapshot.last_prompt_tokens == 90
    assert snapshot.last_completion_tokens == 10
    assert snapshot.last_total_tokens == 100
    assert snapshot.turn_count == 2


def test_builtin_usage_metrics_hook_cleans_session_state_on_shutdown() -> None:
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
    assert get_session_usage_snapshot(registry=registry, session_id="sess_usage_2") is not None

    asyncio.run(
        runner.dispatch_observe(
            "session_shutdown",
            {"session_id": "sess_usage_2"},
            HookContext(session_id="sess_usage_2"),
        )
    )
    assert get_session_usage_snapshot(registry=registry, session_id="sess_usage_2") is None


def test_builtin_usage_metrics_prefers_latest_usage_for_last_counters() -> None:
    registry = _build_registry_with_usage_hook()
    runner = HookRunner(registry=registry)

    asyncio.run(
        runner.dispatch_observe(
            "turn_end",
            {
                "session_id": "sess_usage_3",
                "turn_id": "turn_1",
                "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200},
                "latest_usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
            },
            HookContext(session_id="sess_usage_3", turn_id="turn_1"),
        )
    )

    snapshot = get_session_usage_snapshot(registry=registry, session_id="sess_usage_3")
    assert snapshot is not None
    assert snapshot.total_tokens == 1200
    assert snapshot.last_prompt_tokens == 120
    assert snapshot.last_completion_tokens == 30
    assert snapshot.last_total_tokens == 150
