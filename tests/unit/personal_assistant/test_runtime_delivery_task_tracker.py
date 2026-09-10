"""Lifecycle contract for detached runtime-delivery tasks."""

from __future__ import annotations

import asyncio

import pytest

from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)
from personal_assistant.gateway.runtime_delivery.context import (
    RunDeliveryContext,
    RunDeliveryContextStore,
    RunDeliveryTarget,
)


@pytest.mark.asyncio
async def test_terminal_context_survives_upload_and_reset_revokes_late_publish() -> (
    None
):
    store = RunDeliveryContextStore()
    context = store.seed(
        RunDeliveryContext(
            run_id="run-1",
            agent_id="agent",
            kernel_session_id="kernel",
            delivery_target=RunDeliveryTarget.none(),
        )
    )
    store.register_session("run-1", "chat", 0)
    tracker = RuntimeDeliveryTaskTracker(context_store=store)
    release = asyncio.Event()
    completed: list[bool] = []

    async def upload() -> None:
        await release.wait()
        completed.append(tracker.admit_publication("run-1"))

    tracker.start(upload(), name="image-upload", run_id="run-1", preserve_on_reset=True)
    assert store.take("run-1") is context
    assert store.get("run-1") is context
    assert store.retained_run_ids("chat", 0) == ("run-1",)
    store.quiesce("run-1")
    await asyncio.wait_for(tracker.drain_admitted(("run-1",)), timeout=1)
    store.advance_generation("chat", 1)
    tracker.cancel_run("run-1")
    release.set()
    await tracker.drain_run("run-1")
    assert completed == [False]
    assert store.get("run-1") is None


@pytest.mark.asyncio
async def test_admitted_drain_waits_only_for_published_requests() -> None:
    store = RunDeliveryContextStore()
    store.seed(
        RunDeliveryContext(
            run_id="run-1",
            agent_id="agent",
            kernel_session_id="kernel",
            delivery_target=RunDeliveryTarget.none(),
        )
    )
    tracker = RuntimeDeliveryTaskTracker(context_store=store)
    assert tracker.admit_publication("run-1")
    store.quiesce("run-1")
    assert not tracker.admit_publication("run-1")
    draining = asyncio.create_task(tracker.drain_admitted(("run-1",)))
    await asyncio.sleep(0)
    assert not draining.done()
    tracker.release_publication("run-1")
    await asyncio.wait_for(draining, timeout=1)
    store.restore("run-1")
    assert tracker.admit_publication("run-1")
    tracker.release_publication("run-1")


def test_late_context_seed_keeps_original_generation_and_is_revoked() -> None:
    store = RunDeliveryContextStore()
    store.register_session("late", "chat", 0)
    store.advance_generation("chat", 1)
    context = store.seed(
        RunDeliveryContext(
            run_id="late",
            agent_id="agent",
            kernel_session_id="kernel",
            delivery_target=RunDeliveryTarget.none(),
        )
    )
    assert context.session_generation == 0
    assert not store.can_publish("late")


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
