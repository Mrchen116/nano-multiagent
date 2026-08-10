import asyncio

import pytest

from agent.core.workflows import (
    WorkflowCompileError,
    WorkflowRuntime,
    compile_workflow,
    execute_workflow,
)


VALID_SOURCE = """
meta = {
    "name": "review",
    "description": "Review inputs",
    "phases": [{"title": "Review", "detail": "Inspect independently"}],
}
LIMIT = 2

async def helper(value):
    return value + LIMIT

async def main():
    phase("Review")
    values = []
    for value in args["values"]:
        values.append(await helper(value))
    return values
"""


def test_compiler_extracts_literal_meta_and_executes_real_python() -> None:
    compiled = compile_workflow(VALID_SOURCE, filename="review.py")

    result = asyncio.run(execute_workflow(compiled, args={"values": [1, 2]}))

    assert compiled.meta.name == "review"
    assert compiled.meta.phases[0].title == "Review"
    assert result.status == "completed"
    assert result.result == [3, 4]


@pytest.mark.parametrize(
    "source, message",
    [
        ("import os\n" + VALID_SOURCE, "import"),
        (VALID_SOURCE.replace("LIMIT = 2", "LIMIT = open('x')"), "open"),
        (
            VALID_SOURCE.replace(
                "async def helper", "class Hidden:\n    pass\n\nasync def helper"
            ),
            "class",
        ),
        (
            VALID_SOURCE.replace("return value + LIMIT", "return value.__class__"),
            "private",
        ),
        (VALID_SOURCE.replace("return value + LIMIT", "return eval('1')"), "eval"),
    ],
)
def test_compiler_rejects_authority_and_dynamic_python(
    source: str, message: str
) -> None:
    with pytest.raises(WorkflowCompileError, match=message):
        compile_workflow(source, filename="blocked.py")


def test_compiler_requires_exactly_one_async_main_and_valid_phase() -> None:
    with pytest.raises(WorkflowCompileError, match="async def main"):
        compile_workflow(VALID_SOURCE.replace("async def main", "def main"))

    compiled = compile_workflow(
        VALID_SOURCE.replace('phase("Review")', 'phase("Unknown")')
    )
    result = asyncio.run(execute_workflow(compiled, args={"values": []}))
    assert result.status == "failed"
    assert "Unknown" in (result.error or "")


def test_unhandled_exception_alone_makes_run_failed() -> None:
    empty = compile_workflow(VALID_SOURCE.replace("return values", "return None"))
    failed = compile_workflow(
        VALID_SOURCE.replace("return values", "raise RuntimeError('boom')")
    )

    assert (
        asyncio.run(execute_workflow(empty, args={"values": []})).status == "completed"
    )
    assert asyncio.run(execute_workflow(failed, args={"values": []})).status == "failed"


def test_sync_helpers_with_control_flow_remain_real_python() -> None:
    source = VALID_SOURCE.replace(
        "async def helper(value):\n    return value + LIMIT",
        "def helper(value):\n    for offset in [LIMIT]:\n        value += offset\n    return value",
    ).replace("await helper(value)", "helper(value)")

    result = asyncio.run(
        execute_workflow(compile_workflow(source), args={"values": [1]})
    )

    assert result.result == [3]


@pytest.mark.asyncio
async def test_continue_cannot_skip_the_cooperative_loop_checkpoint() -> None:
    compiled = compile_workflow(
        """
meta = {"name": "loop", "description": "Checkpoint a continuing loop"}

async def main():
    count = 0
    while count < 3:
        count += 1
        continue
    return count
"""
    )

    async def child(_call):  # noqa: ANN001
        raise AssertionError("loop Workflow must not dispatch a child")

    checkpoints = 0

    class CountingRuntime(WorkflowRuntime):
        async def checkpoint(self) -> None:
            nonlocal checkpoints
            checkpoints += 1
            await super().checkpoint()

    runtime = CountingRuntime(child_runner=child)
    result = await execute_workflow(compiled, args=None, runtime=runtime)

    assert result.result == 3
    assert checkpoints == 4  # async function entry plus each loop iteration
