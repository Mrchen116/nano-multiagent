import asyncio

from agent.core.workflows import (
    ResumeEntry,
    WorkflowRuntime,
    chained_resume_key,
)


def test_chained_v2_key_is_canonical_and_omits_none() -> None:
    left = chained_resume_key(
        "v2",
        "review",
        {"model": "terra", "effort": None, "schema": {"type": "object"}},
    )
    right = chained_resume_key(
        "v2",
        "review",
        {"schema": {"type": "object"}, "model": "terra"},
    )
    changed = chained_resume_key("v2", "review changed", {"model": "terra"})

    assert left == right
    assert left != changed
    assert len(left) == 64


def test_resume_reuses_only_longest_identical_completed_prefix() -> None:
    live: list[str] = []

    async def child(call):  # noqa: ANN001
        live.append(call.prompt)
        return f"live:{call.prompt}"

    async def scenario() -> None:
        first_key = chained_resume_key("v2", "one", {})
        second_key = chained_resume_key(first_key, "two", {})
        third_key = chained_resume_key(second_key, "three", {})
        runtime = WorkflowRuntime(
            child_runner=child,
            resume_entries=(
                ResumeEntry(key=first_key, result="cached:one", terminal_ordinal=0),
                ResumeEntry(key=second_key, result="cached:two", terminal_ordinal=1),
                ResumeEntry(key=third_key, result="cached:three", terminal_ordinal=2),
            ),
        )

        assert await runtime.agent("one") == "cached:one"
        assert await runtime.agent("changed") == "live:changed"
        assert await runtime.agent("three") == "live:three"
        assert live == ["changed", "three"]

    asyncio.run(scenario())


def test_concurrent_cached_results_replay_recorded_terminal_order() -> None:
    async def child(_call):  # noqa: ANN001
        raise AssertionError("a complete resume prefix must not dispatch live")

    async def scenario() -> None:
        first_key = chained_resume_key("v2", "one", {})
        second_key = chained_resume_key(first_key, "two", {})
        runtime = WorkflowRuntime(
            child_runner=child,
            resume_entries=(
                ResumeEntry(key=first_key, result="cached:one", terminal_ordinal=1),
                ResumeEntry(key=second_key, result="cached:two", terminal_ordinal=0),
            ),
        )

        values = await runtime.parallel(
            [lambda: runtime.agent("one"), lambda: runtime.agent("two")]
        )

        assert values == ["cached:one", "cached:two"]
        assert [item.call.prompt for item in runtime.completions] == ["two", "one"]
        assert [item.terminal_ordinal for item in runtime.completions] == [0, 1]

    asyncio.run(scenario())
