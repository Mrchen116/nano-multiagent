"""bugfix-417-M6 (#115): generic tool-execution liveness ticker.

Pre-M6 the only tool that emitted execution heartbeats was bash (its foreground loop
calls ``ctx.emit_execution_event({phase:"running"})`` each tick). Every other
long-running ``to_thread`` tool (e.g. web_fetch) produced zero execution updates for
its whole duration, so a >120s call looked identical to a stall and both watchdogs
reaped the live run — the exact same root cause bash was fixed for in M3/M4.

The fix lifts liveness to the executor's generic layer: ``StreamingToolExecutor``
wraps ``asyncio.to_thread(tool.run, ...)`` in an await-bound ticker that periodically
emits ``{phase:"executing", elapsed_ms}`` through the SAME ``tool_execution_update``
projection chain (realtime_stream → run_heartbeat) bash already rides. These tests
pin the ticker primitive itself: it ticks only while the awaited body is in flight,
carries the executing phase + a growing elapsed_ms, and tears down on every exit path.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agent.core.agent.liveness import execution_update_ticker

pytestmark = pytest.mark.asyncio


def _recorder() -> tuple[list[dict[str, Any]], Any]:
    emitted: list[dict[str, Any]] = []

    def _emit(payload: dict[str, Any]) -> None:
        emitted.append(dict(payload))

    return emitted, _emit


async def test_ticker_emits_executing_phase_with_growing_elapsed() -> None:
    emitted, emit = _recorder()
    async with execution_update_ticker(emit=emit, interval=0.02):
        await asyncio.sleep(0.11)  # ~5 intervals
    count_at_exit = len(emitted)
    assert count_at_exit >= 3, (
        f"expected periodic execution updates, got {count_at_exit}"
    )
    assert all(p["phase"] == "executing" for p in emitted)
    elapsed = [p["elapsed_ms"] for p in emitted]
    assert all(isinstance(e, int) for e in elapsed)
    assert elapsed == sorted(elapsed), f"elapsed_ms must grow monotonically: {elapsed}"
    assert elapsed[0] >= 0

    # await-bound: no further emits after the body exits.
    await asyncio.sleep(0.06)
    assert len(emitted) == count_at_exit, (
        "ticker must stop emitting after the await ends"
    )


async def test_ticker_noop_without_emit() -> None:
    # No emit callable (e.g. CLI without an execution-event sink): create no task,
    # emit nothing, never raise — callers need not branch on availability.
    async with execution_update_ticker(emit=None, interval=0.01):
        await asyncio.sleep(0.05)
    # Reaching here without error is the assertion.


async def test_ticker_torn_down_on_exception() -> None:
    emitted, emit = _recorder()
    with pytest.raises(RuntimeError):
        async with execution_update_ticker(emit=emit, interval=0.02):
            await asyncio.sleep(0.05)
            raise RuntimeError("boom")
    count = len(emitted)
    await asyncio.sleep(0.06)
    assert len(emitted) == count, "ticker must stop even when the body raises"


async def test_ticker_torn_down_on_cancel() -> None:
    emitted, emit = _recorder()

    async def _body() -> None:
        async with execution_update_ticker(emit=emit, interval=0.02):
            await asyncio.sleep(10)  # cancelled mid-flight

    task = asyncio.create_task(_body())
    await asyncio.sleep(0.06)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    count = len(emitted)
    await asyncio.sleep(0.06)
    assert len(emitted) == count, "ticker must stop when the awaited body is cancelled"


async def test_ticker_emit_is_fail_open() -> None:
    # A raising emit (publisher mid-teardown) must never bubble out and crash the
    # awaited tool run; the tick is dropped and the body completes normally.
    calls = {"n": 0}

    def _bad_emit(_payload: dict[str, Any]) -> None:
        calls["n"] += 1
        raise RuntimeError("publisher gone")

    async with execution_update_ticker(emit=_bad_emit, interval=0.02):
        await asyncio.sleep(0.08)
    assert calls["n"] >= 2, "ticker should have attempted several emits"
