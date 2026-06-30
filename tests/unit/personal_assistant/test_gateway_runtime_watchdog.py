"""bugfix-446-M1: GatewayRuntime-level connection resilience.

Covers the watchdog that rebuilds the IM maintenance loop when it exits abnormally
without shutdown (decision 1), startup-order-insensitivity now that the eager
connect_once is gone (decision 3), and the heartbeat first-connect gate that keeps
the feat-393 delivery invariant after the eager connect is removed.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from personal_assistant.main import GatewayRuntime

from ._gateway_runtime_test_utils import make_config, run_in_thread


class _CrashingIMManager:
    """run_forever raises a transient error N times before settling, so the watchdog
    has to rebuild it; records every entry so the test can count rebuilds."""

    def __init__(self, events: list[str], *, crash_times: int) -> None:
        self._events = events
        self._crash_times = crash_times
        self._calls = 0
        self._closed = asyncio.Event()
        self.connected = False

    async def connect_once(self) -> None:  # old-code compat (eager connect path)
        self._events.append("im.connect.eager")

    async def run_forever(self) -> None:
        self._calls += 1
        n = self._calls
        self._events.append(f"run_forever:{n}")
        if n <= self._crash_times:
            raise RuntimeError(f"transient crash {n}")
        self.connected = True
        await self._closed.wait()

    async def wait_first_connect_attempt(self, *, timeout: float = 10.0) -> None:
        return

    async def close(self) -> None:
        self._events.append("im.close")
        self.connected = False
        self._closed.set()


def test_watchdog_rebuilds_im_loop_after_abnormal_exit(tmp_path: Path) -> None:
    """When run_forever exits abnormally (crash or silent return) without shutdown, the
    watchdog must rebuild it — and the crash must never propagate out of the gateway
    (issue path 6 / 'silent death'). Verified by run_forever being entered 3 times
    (2 crashes + 1 stable) and a clean exit 0."""
    events: list[str] = []
    config = make_config(tmp_path)
    manager = _CrashingIMManager(events, crash_times=2)
    runtime = GatewayRuntime(
        config,
        None,
        im_connection_manager=manager,
        im_watchdog_initial_seconds=0.01,
        im_watchdog_max_seconds=0.02,
    )

    thread, outcome = run_in_thread(runtime)
    try:
        assert runtime.wait_until_ready(timeout=2.0) is True
        # Wait for the stable (3rd) entry: 2 crashes rebuilt + 1 that blocks.
        deadline = time.time() + 5.0
        while "run_forever:3" not in events and time.time() < deadline:
            time.sleep(0.02)
        assert "run_forever:3" in events, (
            f"watchdog did not rebuild the loop after abnormal exit; events={events}"
        )
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert "error" not in outcome, (
        f"crash leaked out of gateway: {outcome.get('error')}"
    )
    assert outcome.get("exit_code") == 0
    assert events.count("run_forever:1") == 1
    assert events.count("run_forever:2") == 1


def test_watchdog_does_not_swallow_process_exit_signals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SystemExit/KeyboardInterrupt are process-control signals, not recoverable IM
    faults. The watchdog must re-raise them instead of rebuilding the loop."""

    class _SystemExitIMManager:
        connected = False

        async def run_forever(self) -> None:
            raise SystemExit(2)

    runtime = GatewayRuntime(make_config(tmp_path), None)

    async def _unexpected_rebuild_sleep(_delay: float) -> None:
        raise AssertionError("SystemExit must not enter watchdog rebuild backoff")

    monkeypatch.setattr(
        "personal_assistant.main.asyncio.sleep", _unexpected_rebuild_sleep
    )

    with pytest.raises(SystemExit):
        asyncio.run(runtime._supervise_im_connection(_SystemExitIMManager()))  # noqa: SLF001


def test_watchdog_resets_backoff_after_stable_runtime(tmp_path: Path) -> None:
    """A crash after a long healthy run should restart at the initial watchdog delay,
    not inherit the previous exponential backoff."""

    class _StableThenCrashingIMManager:
        connected = False

        def __init__(self, runtime: GatewayRuntime) -> None:
            self._runtime = runtime
            self.started_at: list[float] = []
            self.calls = 0

        async def run_forever(self) -> None:
            self.calls += 1
            self.started_at.append(time.monotonic())
            if self.calls == 1:
                raise RuntimeError("first crash")
            if self.calls == 2:
                await asyncio.sleep(0.12)
                raise RuntimeError("crash after stable period")
            self._runtime.request_shutdown()

    runtime = GatewayRuntime(
        make_config(tmp_path),
        None,
        im_watchdog_initial_seconds=0.04,
        im_watchdog_max_seconds=0.10,
    )
    manager = _StableThenCrashingIMManager(runtime)

    asyncio.run(runtime._supervise_im_connection(manager))  # noqa: SLF001

    assert manager.calls == 3
    first_backoff = manager.started_at[1] - manager.started_at[0]
    second_backoff = manager.started_at[2] - manager.started_at[1] - 0.12
    assert first_backoff < 0.08
    assert second_backoff < 0.08, (
        "watchdog backoff should reset to the initial delay after a stable run"
    )


def test_watchdog_treats_manager_stop_return_as_clean_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If run_forever returns because the manager was already stopped/closed, the
    watchdog should exit instead of rebuilding forever."""

    class _CleanStoppedIMManager:
        connected = False

        def __init__(self) -> None:
            self._stop_requested = False
            self.calls = 0

        async def run_forever(self) -> None:
            self.calls += 1
            self._stop_requested = True

    runtime = GatewayRuntime(make_config(tmp_path), None)
    manager = _CleanStoppedIMManager()

    async def _unexpected_rebuild_sleep(_delay: float) -> None:
        raise AssertionError(
            "clean manager stop must not enter watchdog rebuild backoff"
        )

    monkeypatch.setattr(
        "personal_assistant.main.asyncio.sleep", _unexpected_rebuild_sleep
    )

    asyncio.run(runtime._supervise_im_connection(manager))  # noqa: SLF001

    assert manager.calls == 1


def test_watchdog_backoff_sleep_is_interrupted_by_shutdown(tmp_path: Path) -> None:
    """Shutdown should interrupt watchdog backoff instead of waiting for the full
    sleep window."""

    class _AlwaysCrashingIMManager:
        connected = False

        def __init__(self) -> None:
            self.calls = 0

        async def run_forever(self) -> None:
            self.calls += 1
            raise RuntimeError("offline")

    async def _exercise() -> None:
        runtime = GatewayRuntime(
            make_config(tmp_path),
            None,
            im_watchdog_initial_seconds=5.0,
            im_watchdog_max_seconds=5.0,
        )
        manager = _AlwaysCrashingIMManager()
        task = asyncio.create_task(runtime._supervise_im_connection(manager))  # noqa: SLF001
        while manager.calls == 0:
            await asyncio.sleep(0)
        runtime.request_shutdown()
        await asyncio.wait_for(task, timeout=0.2)

    asyncio.run(_exercise())


def test_watchdog_backoff_does_not_consume_executor_threads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repeated watchdog backoff timeouts must stay async-native.

    The previous implementation wrapped ``threading.Event.wait`` in
    ``asyncio.to_thread`` for every backoff. Each timeout left one default-executor
    worker blocked until process shutdown, so a flapping IM loop could consume the
    executor.
    """

    from personal_assistant import main as gateway_main

    class _AlwaysCrashingIMManager:
        connected = False

        def __init__(self) -> None:
            self.calls = 0

        async def run_forever(self) -> None:
            self.calls += 1
            raise RuntimeError("offline")

    to_thread_calls = 0

    def _forbidden_to_thread(*_args, **_kwargs):
        nonlocal to_thread_calls
        to_thread_calls += 1
        raise AssertionError("watchdog backoff must not use asyncio.to_thread")

    monkeypatch.setattr(gateway_main.asyncio, "to_thread", _forbidden_to_thread)

    async def _exercise() -> None:
        runtime = GatewayRuntime(
            make_config(tmp_path),
            None,
            im_watchdog_initial_seconds=0.01,
            im_watchdog_max_seconds=0.01,
        )
        manager = _AlwaysCrashingIMManager()
        loop = asyncio.get_running_loop()
        loop.call_later(0.04, runtime.request_shutdown)

        started_at = time.monotonic()
        await asyncio.wait_for(
            runtime._supervise_im_connection(manager),  # noqa: SLF001
            timeout=0.25,
        )
        assert time.monotonic() - started_at < 0.25
        assert manager.calls >= 2

    asyncio.run(_exercise())
    assert to_thread_calls == 0
