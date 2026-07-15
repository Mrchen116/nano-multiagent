"""Public accepted-root lifecycle tests for the Gateway inbound dispatcher."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from personal_assistant.gateway.inbound_dispatcher import InboundDispatcher


class _BlockingPipeline:
    def __init__(self) -> None:
        self.calls: list[Any] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.sealed = False
        self.settle_deadlines: list[float] = []

    async def handle_inbound(self, message: Any) -> None:
        self.calls.append(message)
        self.started.set()
        await self.release.wait()

    def seal(self) -> None:
        self.sealed = True

    async def settle_admission(self, deadline: float) -> None:
        self.settle_deadlines.append(deadline)


@pytest.mark.asyncio
async def test_dispatcher_seal_rejects_new_roots_and_drain_waits_accepted_root() -> None:
    """Same-loop roots accepted before seal drain; later callbacks never enter pipeline."""

    pipeline = _BlockingPipeline()
    dispatcher = InboundDispatcher(pipeline)
    dispatcher.bind_loop(asyncio.get_running_loop())
    dispatcher("accepted")
    await asyncio.wait_for(pipeline.started.wait(), timeout=1)

    deadline = asyncio.get_running_loop().time() + 1
    dispatcher.seal()
    dispatcher("rejected")
    await dispatcher.settle_admission(deadline)
    drain_task = asyncio.create_task(dispatcher.drain(deadline))
    await asyncio.sleep(0)
    assert not drain_task.done()

    pipeline.release.set()
    await drain_task
    assert pipeline.calls == ["accepted"]
    assert pipeline.sealed is True
    assert pipeline.settle_deadlines == [deadline]
    assert not any(
        task.get_name().startswith("inbound-root:")
        for task in asyncio.all_tasks()
        if not task.done()
    )


@pytest.mark.asyncio
async def test_dispatcher_tracks_threadsafe_roots_until_drain() -> None:
    """A callback from another thread remains owned until its pipeline coroutine exits."""

    pipeline = _BlockingPipeline()
    dispatcher = InboundDispatcher(pipeline)
    dispatcher.bind_loop(asyncio.get_running_loop())
    await asyncio.to_thread(dispatcher, "thread-root")
    await asyncio.wait_for(pipeline.started.wait(), timeout=1)

    dispatcher.seal()
    drain_task = asyncio.create_task(
        dispatcher.drain(asyncio.get_running_loop().time() + 1)
    )
    await asyncio.sleep(0)
    assert not drain_task.done()
    pipeline.release.set()
    await drain_task
    assert pipeline.calls == ["thread-root"]
