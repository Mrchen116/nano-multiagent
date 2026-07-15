"""Public accepted-root lifecycle tests for the Gateway inbound dispatcher."""

from __future__ import annotations

import asyncio
import threading
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


@pytest.mark.asyncio
async def test_threadsafe_proxy_cancellation_waits_for_loop_task_cleanup() -> None:
    """Drain cannot return until the loop task acknowledges cancel and cleans up."""

    class _CleanupPipeline(_BlockingPipeline):
        def __init__(self) -> None:
            super().__init__()
            self.cleanup_started = asyncio.Event()
            self.cleanup_release = asyncio.Event()

        async def handle_inbound(self, message: Any) -> None:
            self.calls.append(message)
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cleanup_started.set()
                await self.cleanup_release.wait()
                raise

    pipeline = _CleanupPipeline()
    dispatcher = InboundDispatcher(pipeline)
    dispatcher.bind_loop(asyncio.get_running_loop())
    await asyncio.to_thread(dispatcher, "thread-root")
    await asyncio.wait_for(pipeline.started.wait(), timeout=1)

    drain = asyncio.create_task(
        dispatcher.drain(asyncio.get_running_loop().time() + 0.01)
    )
    await asyncio.wait_for(pipeline.cleanup_started.wait(), timeout=1)
    returned_before_cleanup = drain.done()
    pipeline.cleanup_release.set()
    with pytest.raises(TimeoutError, match="inbound roots exceeded"):
        await drain

    assert returned_before_cleanup is False


@pytest.mark.asyncio
async def test_threadsafe_registration_window_waits_for_loop_task_cleanup() -> None:
    """Drain owns cleanup when its snapshot precedes loop-task registration."""

    class _CleanupPipeline(_BlockingPipeline):
        def __init__(self) -> None:
            super().__init__()
            self.cleanup_started = asyncio.Event()
            self.cleanup_release = asyncio.Event()

        async def handle_inbound(self, message: Any) -> None:
            self.calls.append(message)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cleanup_started.set()
                await self.cleanup_release.wait()
                raise

    pipeline = _CleanupPipeline()
    dispatcher = InboundDispatcher(pipeline)
    dispatcher.bind_loop(asyncio.get_running_loop())
    submitted = threading.Event()

    def _submit_from_thread() -> None:
        dispatcher("thread-root")
        submitted.set()

    thread = threading.Thread(target=_submit_from_thread)
    thread.start()
    # Deliberately block the bound loop until run_coroutine_threadsafe has returned:
    # drain is then queued after the scheduling callback but before the new Task's
    # first step can register itself as a loop root.
    assert submitted.wait(timeout=1)
    thread.join(timeout=1)
    assert not thread.is_alive()

    dispatcher.seal()
    drain = asyncio.create_task(
        dispatcher.drain(asyncio.get_running_loop().time())
    )
    await asyncio.wait_for(pipeline.cleanup_started.wait(), timeout=1)
    await asyncio.sleep(0)
    returned_before_cleanup = drain.done()
    pipeline.cleanup_release.set()
    with pytest.raises(TimeoutError, match="inbound roots exceeded"):
        await drain

    assert returned_before_cleanup is False
    assert not any(
        task.get_name().startswith("inbound-root:")
        for task in asyncio.all_tasks()
        if not task.done()
    )
