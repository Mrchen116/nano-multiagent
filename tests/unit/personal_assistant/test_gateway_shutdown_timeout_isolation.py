"""Shared-deadline timeout isolation across the complete Gateway resource graph."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import socket
import threading
import time

import pytest

from personal_assistant.config.local_store import GatewayLifecycleConfig
from personal_assistant.gateway.inbound_dispatcher import InboundDispatcher
from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
from personal_assistant.gateway.runtime import GatewayRuntime

from ._gateway_runtime_test_utils import make_config, run_in_thread


class _Pipeline:
    def __init__(self, events: list[str], deadlines: list[float]) -> None:
        self.events = events
        self.deadlines = deadlines

    async def handle_inbound(self, _message: object) -> None:
        return

    def seal(self) -> None:
        self.events.append("pipeline.seal")

    async def settle_admission(self, deadline: float) -> None:
        self.events.append("pipeline.settle")
        self.deadlines.append(deadline)


class _Dispatcher(InboundDispatcher):
    def __init__(
        self, pipeline: _Pipeline, events: list[str], deadlines: list[float]
    ) -> None:
        super().__init__(pipeline)
        self.events = events
        self.deadlines = deadlines

    async def drain(self, deadline: float) -> None:
        self.events.append("dispatcher.drain")
        self.deadlines.append(deadline)
        await super().drain(deadline)


class _Heartbeat:
    def __init__(self, events: list[str], deadlines: list[float]) -> None:
        self.events = events
        self.deadlines = deadlines

    async def start(self) -> None:
        self.events.append("heartbeat.start")

    def request_stop(self) -> None:
        self.events.append("heartbeat.seal")

    async def close(self, deadline: float) -> None:
        self.events.append("heartbeat.drain")
        self.deadlines.append(deadline)


class _Cron:
    def __init__(self, events: list[str], deadlines: list[float]) -> None:
        self.events = events
        self.deadlines = deadlines

    def set_gateway_loop(self, _loop: asyncio.AbstractEventLoop) -> None:
        return

    def request_stop(self) -> None:
        self.events.append("cron.seal")

    async def drain_all(self, deadline: float) -> None:
        self.events.append("cron.drain")
        self.deadlines.append(deadline)


class _Owner:
    def __init__(self, name: str, events: list[str], deadlines: list[float]) -> None:
        self.name = name
        self.events = events
        self.deadlines = deadlines

    def seal(self) -> None:
        self.events.append(f"{self.name}.seal")

    async def aclose(self, deadline: float) -> None:
        self.events.append(f"{self.name}.drain")
        self.deadlines.append(deadline)

    async def close_and_drain(self, deadline: float) -> None:
        self.events.append(f"{self.name}.drain")
        self.deadlines.append(deadline)


class _TimeoutCoordinator:
    def __init__(self, events: list[str], deadlines: list[float]) -> None:
        self.events = events
        self.deadlines = deadlines
        self.timed_out = threading.Event()

    async def drain(self, deadline: float) -> None:
        self.events.append("coordinator.drain")
        self.deadlines.append(deadline)
        remaining = max(0.0, deadline - asyncio.get_running_loop().time())
        await asyncio.sleep(remaining + 0.01)
        self.events.append("coordinator.timeout")
        self.timed_out.set()
        raise TimeoutError("coordinator exceeded shared shutdown deadline")


class _Kernel:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def aclose(self) -> None:
        self.events.append("kernel.close")


class _BlockingIM:
    connected = True

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.release_close = threading.Event()
        self.close_started = threading.Event()
        self.close_cancelled = threading.Event()
        self.closed = asyncio.Event()
        self.task_started = threading.Event()
        self.task_cancelled = threading.Event()

    async def wait_first_connect_attempt(self, *, timeout: float = 10.0) -> None:
        del timeout

    async def run_forever(self) -> None:
        self.task_started.set()
        try:
            await self.closed.wait()
        except asyncio.CancelledError:
            self.events.append("im.task.cancelled")
            self.task_cancelled.set()
            raise

    async def close(self) -> None:
        self.events.append("im.close.attempt")
        self.close_started.set()
        try:
            await asyncio.to_thread(self.release_close.wait)
        except asyncio.CancelledError:
            self.events.append("im.close.cancelled")
            self.close_cancelled.set()
            raise
        else:
            self.closed.set()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_timeout_does_not_skip_later_owners_or_reset_deadline(tmp_path) -> None:
    """One real deadline overrun still closes every later owner best-effort."""

    events: list[str] = []
    deadlines: list[float] = []
    pipeline = _Pipeline(events, deadlines)
    coordinator = _TimeoutCoordinator(events, deadlines)
    im = _BlockingIM(events)
    port = _free_port()
    config = replace(
        make_config(tmp_path),
        gateway=GatewayLifecycleConfig(shutdown_grace_seconds=0.25),
    )
    runtime = GatewayRuntime(
        config,
        on_inbound=_Dispatcher(pipeline, events, deadlines),
        heartbeat_runner=_Heartbeat(events, deadlines),
        cron_dispatcher=_Cron(events, deadlines),
        internal_dispatch_handler=InternalDispatchHandler(),
        gateway_internal_port=port,
        kernel=_Kernel(events),
        im_connection_manager=im,
        run_coordinator=coordinator,
        runtime_delivery_tasks=_Owner("delivery", events, deadlines),
        resource_closers=(lambda: events.append("resource.close"),),
    )

    thread, outcome = run_in_thread(runtime)
    assert runtime.wait_until_ready(timeout=2)
    assert im.task_started.wait(timeout=2)
    requested_at = time.monotonic()
    runtime.request_shutdown()

    assert coordinator.timed_out.wait(timeout=2)
    assert im.close_started.wait(timeout=2)
    try:
        assert im.close_cancelled.wait(timeout=1)
    finally:
        im.release_close.set()
        thread.join(timeout=3)

    assert outcome == {"exit_code": 0}
    assert im.task_cancelled.is_set()
    for event in (
        "dispatcher.drain",
        "heartbeat.drain",
        "cron.drain",
        "delivery.drain",
        "im.close.attempt",
        "im.close.cancelled",
        "im.task.cancelled",
        "resource.close",
    ):
        assert event in events
    assert events.index("coordinator.timeout") < events.index("delivery.drain")
    assert events.index("delivery.drain") < events.index("im.close.attempt")
    assert events.index("im.task.cancelled") < events.index("resource.close")
    assert deadlines and len(set(deadlines)) == 1
    assert deadlines[0] == pytest.approx(requested_at + 0.2, abs=0.05)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))
