"""Lifecycle contract for detached runtime-delivery tasks."""

from __future__ import annotations

import asyncio
import inspect

import pytest

from personal_assistant.gateway.runtime_delivery import observer as observer_module
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)


@pytest.mark.asyncio
async def test_close_rejects_admission_and_drains_current_tasks_to_empty() -> None:
    """Close seals new delivery while preserving already accepted work."""

    tracker = RuntimeDeliveryTaskTracker()
    started = asyncio.Event()
    release = asyncio.Event()
    completed: list[str] = []

    async def _deliver() -> None:
        started.set()
        await release.wait()
        completed.append("delivered")

    tracker.start(_deliver(), name="message-delta:run-1")
    await asyncio.wait_for(started.wait(), timeout=1)
    close_task = asyncio.create_task(
        tracker.close_and_drain(asyncio.get_running_loop().time() + 1)
    )
    await asyncio.sleep(0)
    assert not close_task.done()

    late = _deliver()
    with pytest.raises(RuntimeError, match="closed"):
        tracker.start(late, name="late-delta:run-1")
    assert late.cr_frame is None

    release.set()
    await close_task

    assert completed == ["delivered"]
    assert not any(
        task.get_name().startswith("runtime-delivery:")
        for task in asyncio.all_tasks()
        if not task.done()
    )


@pytest.mark.asyncio
async def test_close_timeout_cancels_every_tracked_task_and_names_owner() -> None:
    """A shared deadline cancels leftovers and reports their semantic task names."""

    tracker = RuntimeDeliveryTaskTracker()
    cancelled = {"delta": asyncio.Event(), "tool": asyncio.Event()}

    async def _block(kind: str) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled[kind].set()

    tracker.start(_block("delta"), name="message-delta:run-2")
    tracker.start(_block("tool"), name="tool-terminal:run-2")
    await asyncio.sleep(0)

    with pytest.raises(TimeoutError, match="message-delta:run-2.*tool-terminal:run-2"):
        await tracker.close_and_drain(asyncio.get_running_loop().time())

    assert cancelled["delta"].is_set()
    assert cancelled["tool"].is_set()
    assert not any(
        task.get_name().startswith("runtime-delivery:")
        for task in asyncio.all_tasks()
        if not task.done()
    )


def test_observer_has_no_bare_detached_task_creation() -> None:
    """Observer delegates every detached awaitable to its concrete owner."""

    source = inspect.getsource(observer_module)
    assert ".create_task(" not in source
