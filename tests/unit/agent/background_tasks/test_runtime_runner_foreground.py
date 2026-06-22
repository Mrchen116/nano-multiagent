"""Tests for RuntimeRunner.submit_foreground (bugfix-418).

The foreground subagent path must reuse the kernel's dedicated event loop via
``run_coroutine_threadsafe`` instead of spawning a transient loop with bare
``asyncio.run`` — otherwise a coroutine awaiting a primitive bound to the
dedicated loop (e.g. AgentRuntime's per-session ``asyncio.Lock``) raises
``... is bound to a different event loop``.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future

from agent.platform.background_tasks.runtime_runner import RuntimeRunner


class _StubRuntime:
    """Minimal stand-in; submit_foreground takes a coroutine, not the runtime."""


def _dedicated_loop() -> tuple[asyncio.AbstractEventLoop, threading.Thread]:
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    return loop, thread


def test_submit_foreground_runs_coro_on_injected_loop() -> None:
    loop, _ = _dedicated_loop()
    try:
        runner = RuntimeRunner(runtime=_StubRuntime(), event_loop=loop)

        observed_loop: list[asyncio.AbstractEventLoop] = []

        async def _coro() -> str:
            observed_loop.append(asyncio.get_running_loop())
            return "ok"

        future = runner.submit_foreground(_coro())
        assert isinstance(future, Future)
        assert future.result(timeout=5.0) == "ok"
        # The coroutine ran on the injected dedicated loop, not a transient one.
        assert observed_loop == [loop]
    finally:
        loop.call_soon_threadsafe(loop.stop)


def test_submit_foreground_propagates_exception_through_future() -> None:
    loop, _ = _dedicated_loop()
    try:
        runner = RuntimeRunner(runtime=_StubRuntime(), event_loop=loop)

        async def _boom() -> None:
            raise ValueError("subagent blew up")

        future = runner.submit_foreground(_boom())
        try:
            future.result(timeout=5.0)
            raise AssertionError("expected ValueError to propagate")
        except ValueError as exc:
            assert "subagent blew up" in str(exc)

        # Failure is isolated: the dedicated loop survives and accepts more work.
        async def _again() -> str:
            return "still alive"

        assert runner.submit_foreground(_again()).result(timeout=5.0) == "still alive"
    finally:
        loop.call_soon_threadsafe(loop.stop)


def test_submit_foreground_without_loop_runs_in_isolated_thread() -> None:
    """Defensive fallback when no dedicated loop is wired (pure-library use).

    Must NOT share the caller's loop; runs the coroutine on its own loop.
    """
    runner = RuntimeRunner(runtime=_StubRuntime(), event_loop=None)

    async def _coro() -> str:
        return "fallback ok"

    future = runner.submit_foreground(_coro())
    assert isinstance(future, Future)
    assert future.result(timeout=5.0) == "fallback ok"
