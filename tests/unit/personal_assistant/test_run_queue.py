"""Public shutdown behavior tests for per-session Gateway run queues."""

from __future__ import annotations

import asyncio

import pytest

from personal_assistant.gateway.run_queue import (
    GatewayShutdownBeforeSubmit,
    SessionRunQueue,
    SessionRunQueueSealed,
)


@pytest.mark.asyncio
async def test_seal_cancels_pending_item_and_keeps_active_operation() -> None:
    """Queued-before-submit work fails explicitly while the running head can finish."""

    queue = SessionRunQueue()
    active_started = asyncio.Event()
    release_active = asyncio.Event()
    pending_started = False
    cancelled: list[str] = []

    async def _active() -> str:
        active_started.set()
        await release_active.wait()
        return "active-done"

    async def _pending() -> str:
        nonlocal pending_started
        pending_started = True
        return "pending-done"

    async def _on_cancel(error: GatewayShutdownBeforeSubmit) -> None:
        cancelled.append(error.reason)

    active_task = asyncio.create_task(queue.submit("sess-a", _active))
    await asyncio.wait_for(active_started.wait(), timeout=1)
    pending_task = asyncio.create_task(
        queue.submit("sess-a", _pending, on_cancel=_on_cancel)
    )
    await asyncio.sleep(0)

    queue.seal_and_cancel_pending()
    with pytest.raises(GatewayShutdownBeforeSubmit) as exc_info:
        await pending_task
    await queue.settle_admission(asyncio.get_running_loop().time() + 1)

    assert exc_info.value.reason == "gateway_shutdown_before_submit"
    assert cancelled == ["gateway_shutdown_before_submit"]
    assert pending_started is False
    with pytest.raises(SessionRunQueueSealed):
        await queue.submit("sess-b", _pending)

    release_active.set()
    assert await active_task == "active-done"
    await queue.drain_workers(asyncio.get_running_loop().time() + 1)
    assert not any(
        task.get_name().startswith("session-run-queue:")
        for task in asyncio.all_tasks()
        if not task.done()
    )


@pytest.mark.asyncio
async def test_worker_drain_timeout_cancels_owned_worker() -> None:
    """A queue worker exceeding the absolute deadline is cancelled and does not leak."""

    queue = SessionRunQueue()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _blocked() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    submit_task = asyncio.create_task(queue.submit("sess-timeout", _blocked))
    await asyncio.wait_for(started.wait(), timeout=1)
    queue.seal_and_cancel_pending()

    with pytest.raises(TimeoutError):
        await queue.drain_workers(asyncio.get_running_loop().time() + 0.01)
    await asyncio.wait_for(cancelled.wait(), timeout=1)
    with pytest.raises(asyncio.CancelledError):
        await submit_task
