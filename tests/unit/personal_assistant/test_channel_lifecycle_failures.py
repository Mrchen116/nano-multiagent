"""Managed channel child cleanup, backpressure, and disable regressions."""

from __future__ import annotations

import asyncio
import multiprocessing
import threading
import time
from types import SimpleNamespace

import pytest

from personal_assistant.channels.feishu.worker import (
    FeishuWorkerProcessContext,
    FeishuWorkerRuntime,
    publish_event,
    publish_priority_status,
)
from personal_assistant.gateway.channel_manager import (
    ChannelGeneration,
    ChannelManager,
    ChannelManifest,
    ManagedChannelSpec,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry


def _wait_forever() -> None:
    while True:
        time.sleep(0.05)


class _ProcessAdapter:
    name = "feishu:agent-a"

    def __init__(self, *, fail_start: bool = False) -> None:
        self._process = multiprocessing.get_context("spawn").Process(
            target=_wait_forever
        )
        self.fail_start = fail_start
        self.stopped = 0

    @property
    def alive(self) -> bool:
        return self._process.is_alive() if self._process.pid is not None else False

    def start(self, _handler) -> None:
        self._process.start()
        if self.fail_start:
            raise RuntimeError("partial start")

    def stop(self) -> None:
        self.stopped += 1
        if self._process.pid is None:
            return
        if self._process.is_alive():
            self._process.terminate()
        self._process.join(2)

    def cleanup(self) -> None:
        if self.alive:
            self.stop()


class _RejectingRegistry(ChannelRegistry):
    def register(self, channel, *, replace: bool = False) -> None:
        del channel, replace
        raise RuntimeError("registry unavailable")


def _spec(*, revision: int = 1, enabled: bool = True) -> ManagedChannelSpec:
    return ManagedChannelSpec(
        channel_id="ch-a",
        agent_id="agent-a",
        provider="feishu",
        enabled=enabled,
        config={"app_id": "cli_a"},
        credentials={"app_secret": "secret-a"},
        provider_runtime={},
        generation=ChannelGeneration(
            provider_identity_fingerprint="fp-a",
            provider_identity_revision=1,
            channel_revision=revision,
            credential_revision=1,
        ),
        credential_envelope={"ciphertext": "opaque"},
        credential_key_id="key-a",
    )


@pytest.mark.parametrize("failure", ["start", "registry"])
def test_partial_start_and_registry_failure_reap_candidate_child(failure: str) -> None:
    """Every failure after candidate construction invokes its stop exactly once."""
    adapter = _ProcessAdapter(fail_start=failure == "start")
    registry = _RejectingRegistry() if failure == "registry" else ChannelRegistry()
    manager = ChannelManager(
        registry=registry,
        on_inbound=lambda _message: None,
        provider_factories={"feishu": lambda _spec, _binder, _status: adapter},
        status_sink=lambda _status: None,
    )
    try:
        result = asyncio.run(
            manager.reconcile(ChannelManifest(manifest_revision=1, channels=(_spec(),)))
        )
        assert result.failed_channel_ids == ("ch-a",)
        assert adapter.stopped == 1
        assert adapter.alive is False
    finally:
        adapter.cleanup()


def _noncooperative_pressure_worker(context: FeishuWorkerProcessContext) -> None:
    publish_event(context, {"index": 0}, timeout=0.1)
    for index in range(1, 6):
        if not publish_event(context, {"index": index}, timeout=0.05):
            break
    while True:
        time.sleep(0.05)


def _stable_worker(context: FeishuWorkerProcessContext) -> None:
    publish_priority_status(context, connection_state="connected")
    while not context.stop_event.wait(0.05):
        pass


class _WorkerAdapter:
    name = "feishu:agent-a"

    def __init__(self, *, target, status_handler, block_events: bool) -> None:
        self._release = threading.Event()

        def on_event(_event) -> None:
            if block_events:
                self._release.wait()

        self.runtime = FeishuWorkerRuntime(
            app_id="cli_pressure",
            app_secret="secret",
            incarnation=f"inc-{time.time_ns()}",
            on_event=on_event,
            on_status=lambda status: status_handler(
                status_sequence=status.status_sequence,
                connection_state=status.connection_state,
                status_code=status.status_code,
                status_message=status.status_message,
            ),
            worker_target=target,
            multiprocessing_context=multiprocessing.get_context("spawn"),
            event_queue_capacity=1,
            join_timeout=0.2,
        )
        ready_event = self.runtime._ready_event
        self.runtime._ready_event = SimpleNamespace(
            wait=lambda _default_timeout: ready_event.wait(30)
        )

    def start(self, _handler) -> None:
        self.runtime.start()

    def stop(self) -> None:
        self._release.set()
        self.runtime.stop(drain=True)

    def stop_invalidated(self) -> None:
        self._release.set()
        self.runtime.stop(drain=False)


class _ImmediateStatusAdapter:
    name = "feishu:agent-a"

    def __init__(self, *, status_handler, pressure: bool) -> None:
        self._status_handler = status_handler
        self._pressure = pressure
        self.stopped = False

    def start(self, _handler) -> None:
        if self._pressure:
            self._status_handler(
                status_sequence=2,
                connection_state="failed",
                status_code="event_backpressure",
            )

    def stop(self) -> None:
        self.stopped = True

    def stop_invalidated(self) -> None:
        self.stop()


def _wait_until(predicate, *, timeout: float = 4.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met before timeout")


def test_backpressure_reaps_noncooperative_listener_and_restarts_once() -> None:
    """A full FIFO cannot leave the SDK listener alive after terminal status."""
    adapters: list[_WorkerAdapter] = []
    statuses = []

    def factory(_spec, _binder, status_handler):
        first = not adapters
        adapter = _WorkerAdapter(
            target=_noncooperative_pressure_worker if first else _stable_worker,
            status_handler=status_handler,
            block_events=first,
        )
        adapters.append(adapter)
        return adapter

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={"feishu": factory},
        status_sink=statuses.append,
    )
    try:
        asyncio.run(
            manager.reconcile(ChannelManifest(manifest_revision=1, channels=(_spec(),)))
        )
        _wait_until(
            lambda: (
                len(adapters) == 2
                and any(
                    status.status_code == "event_backpressure" for status in statuses
                )
                and adapters[0].runtime.is_alive is False
                and manager.registry.get("feishu:agent-a") is adapters[1]
            ),
            timeout=45,
        )
        assert len(adapters) == 2
    finally:
        asyncio.run(manager.close())


def test_backpressure_retry_budget_reaps_final_listener() -> None:
    """Three retries end failed with no child and no extra automatic restart."""
    adapters: list[_WorkerAdapter] = []

    def factory(_spec, _binder, status_handler):
        pressure = len(adapters) < 4
        adapter = _WorkerAdapter(
            target=_noncooperative_pressure_worker if pressure else _stable_worker,
            status_handler=status_handler,
            block_events=pressure,
        )
        adapters.append(adapter)
        return adapter

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={"feishu": factory},
        status_sink=lambda _status: None,
    )
    try:
        asyncio.run(
            manager.reconcile(ChannelManifest(manifest_revision=1, channels=(_spec(),)))
        )
        # Four spawn/reap cycles are intentionally sequential; leave headroom for
        # loaded CI workers without adding delay to the successful path.
        _wait_until(
            lambda: (
                len(adapters) == 4
                and manager.registry.get("feishu:agent-a") is None
                and all(not item.runtime.is_alive for item in adapters)
            ),
            timeout=45,
        )
        time.sleep(0.6)
        assert len(adapters) == 4
    finally:
        asyncio.run(manager.close())


def test_manual_retry_after_retry_exhaustion_uses_retained_desired() -> None:
    """A manual reconnect can reuse desired state after automatic retries stop."""
    adapters: list[_ImmediateStatusAdapter] = []

    def factory(_spec, _binder, status_handler):
        adapter = _ImmediateStatusAdapter(
            status_handler=status_handler,
            pressure=len(adapters) < 4,
        )
        adapters.append(adapter)
        return adapter

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={"feishu": factory},
        status_sink=lambda _status: None,
    )
    try:
        asyncio.run(
            manager.reconcile(ChannelManifest(manifest_revision=1, channels=(_spec(),)))
        )
        _wait_until(
            lambda: (
                len(adapters) == 4
                and manager.registry.get("feishu:agent-a") is None
                and all(adapter.stopped for adapter in adapters)
            )
        )

        asyncio.run(manager.reconnect("ch-a"))

        assert len(adapters) == 5
        assert manager.registry.get("feishu:agent-a") is adapters[4]
        assert adapters[4].stopped is False
    finally:
        asyncio.run(manager.close())


class _SlowStopAdapter:
    name = "feishu:agent-a"

    def start(self, _handler) -> None:
        pass

    def stop(self) -> None:
        time.sleep(0.3)


def test_manual_reconnect_does_not_block_gateway_event_loop() -> None:
    """Heartbeat/ACK coroutines can run while the old listener joins."""
    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={
            "feishu": lambda _spec, _binder, _status: _SlowStopAdapter()
        },
        status_sink=lambda _status: None,
    )
    asyncio.run(
        manager.reconcile(ChannelManifest(manifest_revision=1, channels=(_spec(),)))
    )

    async def exercise() -> float:
        started = time.monotonic()
        reconnect = asyncio.create_task(manager.reconnect("ch-a"))
        await asyncio.sleep(0.03)
        elapsed = time.monotonic() - started
        await reconnect
        return elapsed

    assert asyncio.run(exercise()) < 0.1


def test_disable_emits_one_new_generation_barrier_and_reenable_starts_once() -> None:
    """Observed disabled is emitted once after stop, then enable reuses the secret."""
    statuses = []
    events: list[str] = []

    class Adapter:
        name = "feishu:agent-a"

        def start(self, _handler) -> None:
            events.append("start")

        def stop(self) -> None:
            events.append("stop")

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={"feishu": lambda _spec, _b, _s: Adapter()},
        status_sink=statuses.append,
    )
    asyncio.run(
        manager.reconcile(ChannelManifest(manifest_revision=1, channels=(_spec(),)))
    )
    asyncio.run(
        manager.reconcile(
            ChannelManifest(
                manifest_revision=2,
                channels=(_spec(revision=2, enabled=False),),
            )
        )
    )
    disabled = [
        status
        for status in statuses
        if status.generation.channel_revision == 2
        and status.connection_state == "disabled"
    ]
    assert len(disabled) == 1
    assert disabled[0].instance_started is True
    assert disabled[0].status_sequence == 1

    asyncio.run(
        manager.reconcile(
            ChannelManifest(
                manifest_revision=3,
                channels=(_spec(revision=3, enabled=True),),
            )
        )
    )
    assert events == ["start", "stop", "start"]
