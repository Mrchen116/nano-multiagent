"""GatewayRuntime startup, heartbeat gate, and shutdown cleanup resilience."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.main import GatewayRuntime
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._gateway_runtime_test_utils import make_config, run_in_thread
from ._im_connection_helpers import _minimal_reporter


class _GateFakeIM:
    """Resolve the first-connect signal only after a delay.

    Heartbeat startup must wait for that resolution before its first tick.
    """

    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._closed = asyncio.Event()
        self._resolved = asyncio.Event()
        self.connected = False

    async def connect_once(self) -> None:
        self._events.append("im.connect.eager")

    async def run_forever(self) -> None:
        await asyncio.sleep(0.05)
        self.connected = True
        self._events.append("im.connect.resolved")
        self._resolved.set()
        await self._closed.wait()

    async def wait_first_connect_attempt(self, *, timeout: float = 10.0) -> None:
        try:
            await asyncio.wait_for(self._resolved.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return

    async def close(self) -> None:
        self._events.append("im.close")
        self._closed.set()


class _RecordingHeartbeatRunner:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def start(self) -> None:
        self._events.append("heartbeat.start")

    async def close(self) -> None:
        self._events.append("heartbeat.close")


def test_gateway_survives_unreachable_im_at_startup(tmp_path: Path) -> None:
    """Gateway reaches ready even when IM is unreachable at startup."""

    config = make_config(tmp_path)
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)

    async def _connect(url: str, headers: dict[str, str]):  # noqa: ARG001
        raise RuntimeError("offline")

    manager = IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local:9000",
            reconnect_initial_seconds=0.01,
            reconnect_max_seconds=0.02,
        ),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        connect=_connect,
    )
    runtime = GatewayRuntime(config, None, im_connection_manager=manager)

    thread, outcome = run_in_thread(runtime)
    try:
        assert runtime.wait_until_ready(timeout=2.0) is True
        time.sleep(0.2)
        assert thread.is_alive() is True
        assert "error" not in outcome
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert outcome.get("exit_code") == 0, (
        f"gateway must survive unreachable IM at startup; outcome={outcome}"
    )


def test_heartbeat_start_waits_for_first_connect_attempt(tmp_path: Path) -> None:
    """Heartbeat startup waits until the first connect attempt has resolved."""

    events: list[str] = []
    manager = _GateFakeIM(events)
    heartbeat = _RecordingHeartbeatRunner(events)
    runtime = GatewayRuntime(
        make_config(tmp_path),
        None,
        im_connection_manager=manager,
        heartbeat_runner=heartbeat,
    )

    thread, outcome = run_in_thread(runtime)
    try:
        deadline = time.time() + 3.0
        while "heartbeat.start" not in events and time.time() < deadline:
            time.sleep(0.01)
        assert "heartbeat.start" in events, f"heartbeat never started; events={events}"
        assert "im.connect.resolved" in events
        assert events.index("im.connect.resolved") < events.index("heartbeat.start"), (
            f"heartbeat must start only after first connect resolution; events={events}"
        )
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert outcome.get("exit_code") == 0


def test_shutdown_cleanup_continues_when_im_task_await_raises_base_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CancelledError from IM task cleanup must not skip later shutdown steps."""

    from personal_assistant import main as gateway_main

    events: list[str] = []

    class _FakeProcessManager:
        def start_kernel_process(self) -> None:
            events.append("kernel.start")

        def stop_kernel_process(self) -> None:
            events.append("kernel.stop")

    async def _raise_cancelled(_task: asyncio.Task[None]) -> None:
        events.append("await.im_task")
        raise asyncio.CancelledError()

    monkeypatch.setattr(gateway_main, "_await_background_task", _raise_cancelled)

    manager = _GateFakeIM(events)
    runtime = GatewayRuntime(
        make_config(tmp_path),
        _FakeProcessManager(),
        im_connection_manager=manager,
        resource_closers=(lambda: events.append("resource.close"),),
    )

    thread, outcome = run_in_thread(runtime)
    try:
        assert runtime.wait_until_ready(timeout=2.0) is True
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert outcome.get("exit_code") == 0
    assert "error" not in outcome
    assert "kernel.stop" in events
    assert "resource.close" in events


def test_shutdown_cleanup_continues_when_im_close_raises(tmp_path: Path) -> None:
    """An IM close failure must not skip process stop, resource closers, or exit 0."""

    events: list[str] = []

    class _CloseRaisesIM(_GateFakeIM):
        async def close(self) -> None:
            events.append("im.close")
            self._closed.set()
            raise RuntimeError("close failed")

    class _FakeProcessManager:
        def start_kernel_process(self) -> None:
            events.append("kernel.start")

        def stop_kernel_process(self) -> None:
            events.append("kernel.stop")

    manager = _CloseRaisesIM(events)
    runtime = GatewayRuntime(
        make_config(tmp_path),
        _FakeProcessManager(),
        im_connection_manager=manager,
        resource_closers=(lambda: events.append("resource.close"),),
    )

    thread, outcome = run_in_thread(runtime)
    try:
        assert runtime.wait_until_ready(timeout=2.0) is True
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert outcome.get("exit_code") == 0
    assert "error" not in outcome
    assert "im.close" in events
    assert "kernel.stop" in events
    assert "resource.close" in events
