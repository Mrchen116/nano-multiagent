"""Gateway shutdown ownership graph and one-deadline contract."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import socket
import threading
import time
from typing import Any

import pytest

from personal_assistant.config.local_store import (
    GatewayLifecycleConfig,
    HeartbeatConfig,
)
from personal_assistant.gateway.inbound_dispatcher import InboundDispatcher
from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
from personal_assistant.gateway.runtime import GatewayRuntime
from personal_assistant.main import PollingHeartbeatRunner

from ._gateway_runtime_test_utils import make_config, run_in_thread


class _PipelineOwner:
    def __init__(self, events: list[str], deadlines: list[float]) -> None:
        self.events = events
        self.deadlines = deadlines

    async def handle_inbound(self, _message: object) -> None:
        return

    def seal(self) -> None:
        self.events.append("pipeline.seal")

    async def settle_admission(self, deadline: float) -> None:
        self.events.append("dispatcher.settle")
        self.deadlines.append(deadline)


class _ConsumerOwner:
    def __init__(self, name: str, events: list[str], deadlines: list[float]) -> None:
        self.name = name
        self.events = events
        self.deadlines = deadlines

    def seal_and_cancel_pending(self) -> None:
        self.events.append(f"{self.name}.seal")

    def seal(self) -> None:
        self.events.append(f"{self.name}.seal")

    async def drain_workers(self, deadline: float) -> None:
        self.events.append(f"{self.name}.drain")
        self.deadlines.append(deadline)

    async def aclose(self, deadline: float) -> None:
        self.events.append(f"{self.name}.drain")
        self.deadlines.append(deadline)

    async def close_and_drain(self, deadline: float) -> None:
        self.events.append(f"{self.name}.drain")
        self.deadlines.append(deadline)

    async def drain(self, deadline: float) -> None:
        self.events.append(f"{self.name}.drain")
        self.deadlines.append(deadline)


class _HeartbeatOwner:
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


class _CronOwner:
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


class _InternalOwner:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def seal(self) -> None:
        self.events.append("internal.seal")


class _Kernel:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.closed = threading.Event()

    async def aclose(self) -> None:
        self.events.append("kernel.close")
        self.closed.set()


class _IM:
    connected = True

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.closed = asyncio.Event()

    async def run_forever(self) -> None:
        await self.closed.wait()

    async def wait_first_connect_attempt(self, *, timeout: float = 10.0) -> None:
        del timeout

    async def close(self) -> None:
        self.events.append("im.close")
        self.closed.set()


def test_shutdown_seals_then_closes_kernel_and_drains_one_deadline(tmp_path) -> None:
    events: list[str] = []
    deadlines: list[float] = []
    pipeline = _PipelineOwner(events, deadlines)
    dispatcher = InboundDispatcher(pipeline)
    heartbeat = _HeartbeatOwner(events, deadlines)
    cron = _CronOwner(events, deadlines)
    coordinator = _ConsumerOwner("coordinator", events, deadlines)
    delivery = _ConsumerOwner("delivery", events, deadlines)
    internal = _InternalOwner(events)
    kernel = _Kernel(events)
    im = _IM(events)
    config = replace(
        make_config(tmp_path),
        gateway=GatewayLifecycleConfig(shutdown_grace_seconds=1.0),
    )
    runtime = GatewayRuntime(
        config,
        on_inbound=dispatcher,
        heartbeat_runner=heartbeat,
        cron_dispatcher=cron,
        internal_dispatch_handler=internal,
        kernel=kernel,
        im_connection_manager=im,
        run_coordinator=coordinator,
        runtime_delivery_tasks=delivery,
    )

    thread, outcome = run_in_thread(runtime)
    assert runtime.wait_until_ready(timeout=2)
    requested_at = time.monotonic()
    runtime.request_shutdown()
    thread.join(timeout=3)

    assert outcome == {"exit_code": 0}
    assert events.index("pipeline.seal") < events.index("dispatcher.settle")
    assert events.index("internal.seal") < events.index("kernel.close")
    assert events.index("heartbeat.seal") < events.index("kernel.close")
    assert events.index("cron.seal") < events.index("kernel.close")
    assert events.index("dispatcher.settle") < events.index("kernel.close")
    for owner in ("heartbeat", "cron", "coordinator"):
        assert events.index("kernel.close") < events.index(f"{owner}.drain")
        assert events.index(f"{owner}.drain") < events.index("delivery.drain")
    assert events.index("delivery.drain") < events.index("im.close")
    assert deadlines and len(set(deadlines)) == 1
    assert deadlines[0] == pytest.approx(requested_at + 0.8, abs=0.1)


class _FailingDispatcher(InboundDispatcher):
    def __init__(self, pipeline: Any, events: list[str]) -> None:
        super().__init__(pipeline)
        self.events = events

    async def drain(self, deadline: float) -> None:
        del deadline
        self.events.append("dispatcher.drain.failed")
        raise RuntimeError("root drain failed")


def test_one_consumer_failure_does_not_skip_other_drains(tmp_path) -> None:
    events: list[str] = []
    deadlines: list[float] = []
    pipeline = _PipelineOwner(events, deadlines)
    runtime = GatewayRuntime(
        make_config(tmp_path),
        on_inbound=_FailingDispatcher(pipeline, events),
        heartbeat_runner=_HeartbeatOwner(events, deadlines),
        cron_dispatcher=_CronOwner(events, deadlines),
        kernel=_Kernel(events),
        im_connection_manager=_IM(events),
        run_coordinator=_ConsumerOwner("coordinator", events, deadlines),
        runtime_delivery_tasks=_ConsumerOwner("delivery", events, deadlines),
    )

    thread, outcome = run_in_thread(runtime)
    assert runtime.wait_until_ready(timeout=2)
    runtime.request_shutdown()
    thread.join(timeout=3)

    assert outcome == {"exit_code": 0}
    assert "dispatcher.drain.failed" in events
    assert "coordinator.drain" in events
    assert "delivery.drain" in events
    assert "im.close" in events


class _BlockingDispatchManager:
    connected = True

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    async def send_agent_message(self, _payload: object):
        self.started.set()
        await asyncio.to_thread(self.release.wait)
        return _DispatchAck()


class _DispatchAck:
    def as_dict(self) -> dict[str, str]:
        return {"message_id": "msg-1"}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
async def test_active_internal_http_handler_does_not_block_kernel_close(
    tmp_path,
) -> None:
    from aiohttp import ClientSession

    manager = _BlockingDispatchManager()
    kernel = _Kernel([])
    port = _free_port()
    runtime = GatewayRuntime(
        make_config(tmp_path),
        internal_dispatch_handler=InternalDispatchHandler(
            im_connection_manager=manager
        ),
        gateway_internal_port=port,
        kernel=kernel,
    )
    thread, outcome = run_in_thread(runtime)
    assert runtime.wait_until_ready(timeout=2)

    async with ClientSession() as session:
        request = asyncio.create_task(
            session.post(
                f"http://127.0.0.1:{port}/internal/dispatch",
                json={"text": "hello", "to": "agent-b"},
            )
        )
        assert await asyncio.to_thread(manager.started.wait, 2)
        runtime.request_shutdown()
        try:
            assert await asyncio.to_thread(kernel.closed.wait, 0.5)
        finally:
            manager.release.set()
        response = await asyncio.wait_for(request, timeout=2)
        assert response.status == 200

    thread.join(timeout=3)
    assert outcome == {"exit_code": 0}


@pytest.mark.asyncio
async def test_heartbeat_seal_preserves_current_tick_until_deadline_drain() -> None:
    class _BlockingScheduler:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def tick(self) -> None:
            self.started.set()
            await self.release.wait()

    scheduler = _BlockingScheduler()
    runner = PollingHeartbeatRunner(
        scheduler=scheduler,  # type: ignore[arg-type]
        config=HeartbeatConfig(tick_interval_seconds=60),
    )
    await runner.start()
    await asyncio.wait_for(scheduler.started.wait(), timeout=1)

    runner.request_stop()
    close = asyncio.create_task(runner.close(asyncio.get_running_loop().time() + 1))
    await asyncio.sleep(0)
    assert not close.done()

    scheduler.release.set()
    await close
    assert not any(
        task.get_name() == "personal-assistant-heartbeat"
        for task in asyncio.all_tasks()
        if not task.done()
    )


def test_active_heartbeat_drain_does_not_block_kernel_close(tmp_path) -> None:
    class _BlockingHeartbeat(_HeartbeatOwner):
        def __init__(self, events: list[str], deadlines: list[float]) -> None:
            super().__init__(events, deadlines)
            self.close_started = threading.Event()
            self.release = threading.Event()

        async def close(self, deadline: float) -> None:
            self.events.append("heartbeat.drain")
            self.deadlines.append(deadline)
            self.close_started.set()
            await asyncio.to_thread(self.release.wait)

    events: list[str] = []
    deadlines: list[float] = []
    heartbeat = _BlockingHeartbeat(events, deadlines)
    kernel = _Kernel(events)
    runtime = GatewayRuntime(
        make_config(tmp_path),
        heartbeat_runner=heartbeat,
        kernel=kernel,
    )
    thread, outcome = run_in_thread(runtime)
    assert runtime.wait_until_ready(timeout=2)
    runtime.request_shutdown()
    assert kernel.closed.wait(timeout=0.5)
    assert heartbeat.close_started.wait(timeout=0.5)
    assert thread.is_alive()

    heartbeat.release.set()
    thread.join(timeout=3)
    assert outcome == {"exit_code": 0}


@pytest.mark.asyncio
async def test_cron_seal_rejects_late_work_and_drains_current_execution(
    tmp_path,
) -> None:
    from personal_assistant.scheduler.cron_execution_service import (
        CronExecutionService,
    )
    from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

    started = asyncio.Event()
    release = asyncio.Event()

    async def _execute(**_kwargs: object) -> None:
        started.set()
        await release.wait()

    CronJobStore(workspace_root=tmp_path).add(
        CronJob(
            id="job-1",
            name="shutdown lifecycle",
            schedule={"kind": "every", "everyMs": 60_000},
            instruction="test",
        )
    )
    service = CronExecutionService(
        agent_id="agent-a",
        workspace_root=tmp_path,
        execute_fn=_execute,
    )
    assert service.enqueue(job_id="job-1", trigger="manual")["accepted"] is True
    await asyncio.wait_for(started.wait(), timeout=1)

    service.request_stop()
    late = service.enqueue(job_id="job-1", trigger="manual")
    assert late["accepted"] is False
    assert late["error_code"] == "cron_unavailable"

    close = asyncio.create_task(service.drain(asyncio.get_running_loop().time() + 1))
    await asyncio.sleep(0)
    assert not close.done()
    release.set()
    await close
