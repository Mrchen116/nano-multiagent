import asyncio

import pytest

from agent.core.workflows import WorkflowLimits, WorkflowRuntime, WorkflowStopped


def test_agent_reserves_global_start_ordinal_before_await() -> None:
    started: list[tuple[int, str]] = []

    async def child(call):  # noqa: ANN001
        started.append((call.start_ordinal, call.prompt))
        await asyncio.sleep(0)
        return call.prompt.upper()

    async def scenario() -> None:
        runtime = WorkflowRuntime(child_runner=child)
        second = runtime.agent("second")
        first = runtime.agent("first")
        results = await runtime.parallel([lambda: second, lambda: first])
        assert results == ["SECOND", "FIRST"]
        assert started == [(0, "second"), (1, "first")]

    asyncio.run(scenario())


def test_parallel_is_position_preserving_barrier_and_errors_become_none() -> None:
    async def child(call):  # noqa: ANN001
        if call.prompt == "bad":
            raise RuntimeError("nope")
        await asyncio.sleep(0.01 if call.prompt == "slow" else 0)
        return call.prompt

    async def scenario() -> None:
        runtime = WorkflowRuntime(child_runner=child)
        results = await runtime.parallel(
            [
                lambda: runtime.agent("slow"),
                lambda: (_ for _ in ()).throw(RuntimeError("thunk")),
                lambda: runtime.agent("bad"),
                lambda: runtime.agent("fast"),
            ]
        )
        assert results == ["slow", None, None, "fast"]

    asyncio.run(scenario())


def test_pipeline_flows_each_item_without_cross_stage_barrier() -> None:
    calls: list[str] = []

    async def child(call):  # noqa: ANN001
        calls.append(call.prompt)
        if call.prompt == "s1:bad":
            raise RuntimeError("bad item")
        if call.prompt == "s1:slow":
            await asyncio.sleep(0.02)
        return call.prompt

    async def scenario() -> None:
        runtime = WorkflowRuntime(child_runner=child)
        results = await runtime.pipeline(
            ["slow", "fast", "bad"],
            lambda _previous, original, _index: runtime.agent(f"s1:{original}"),
            lambda previous, _original, _index: runtime.agent(f"s2:{previous}"),
        )
        assert results == ["s2:s1:slow", "s2:s1:fast", None]
        assert calls.index("s2:s1:fast") < calls.index("s2:s1:slow")
        assert all(not value.startswith("s2:s1:bad") for value in calls)

    asyncio.run(scenario())


def test_parallel_thunks_are_sync_and_limits_fail_explicitly() -> None:
    async def child(call):  # noqa: ANN001
        return call.prompt

    async def async_thunk():
        return "not allowed"

    async def scenario() -> None:
        runtime = WorkflowRuntime(
            child_runner=child,
            limits=WorkflowLimits(max_agents=1, max_items=2, max_concurrency=1),
        )
        with pytest.raises(ValueError, match="synchronous thunk"):
            await runtime.parallel([async_thunk])
        with pytest.raises(ValueError, match="4096|items"):
            await runtime.parallel([lambda: None, lambda: None, lambda: None])
        await runtime.agent("one")
        with pytest.raises(ValueError, match="1000|Agent"):
            runtime.agent("two")

    asyncio.run(scenario())


def test_pause_blocks_new_effect_and_stop_wins_top_level_status() -> None:
    started = asyncio.Event()

    async def child(call):  # noqa: ANN001
        started.set()
        return call.prompt

    async def scenario() -> None:
        runtime = WorkflowRuntime(child_runner=child)
        runtime.pause()
        call = runtime.agent("later")

        async def wait_for_call():  # noqa: ANN202
            return await call

        task = asyncio.create_task(wait_for_call())
        await asyncio.sleep(0)
        assert not started.is_set()
        runtime.stop()
        with pytest.raises(WorkflowStopped):
            await task

    asyncio.run(scenario())
