"""Reset publication must fence pending output without waiting for image preparation."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.gateway.inbound_models import (
    InboundRunRequest,
    NewSessionRequest,
    RoutedInbound,
    StopRunRequest,
)
from personal_assistant.gateway.runtime_delivery.context import RunDeliveryContextStore
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)
from personal_assistant.gateway.runtime_delivery.lifecycle import (
    build_relay_lifecycle_callback,
)
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from ._session_run_coordinator_helpers import build_dependencies, inbound


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", [False, True])
@pytest.mark.parametrize("reset_fails", [False, True])
async def test_new_decides_before_upload_finishes_and_fences_retained_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal: bool,
    reset_fails: bool,
) -> None:
    kernel, catalog, binder, router, _ = build_dependencies(tmp_path)
    store = RunDeliveryContextStore()
    tracker = RuntimeDeliveryTaskTracker(context_store=store)
    upload_release = asyncio.Event()
    outcomes: list[bool] = []

    async def upload(run_id: str) -> None:
        await upload_release.wait()
        visible = await store.await_visibility(run_id)
        admitted = visible and tracker.admit_publication(run_id)
        outcomes.append(admitted)
        if admitted:
            tracker.release_publication(run_id)

    async def lifecycle(routed, update) -> None:
        if update.phase == "accepted":
            context = store.seed_from_lifecycle(
                routed=routed, update=update, owner_user_id="owner"
            )
            assert context is not None
            tracker.start(
                upload(context.run_id),
                name="prepare-images",
                run_id=context.run_id,
                preserve_on_reset=True,
            )
        elif update.phase in {"completed", "failed"}:
            store.take(update.run_id)

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        relay_lifecycle_callback=lifecycle,
        delivery_context_store=store,
        drain_admitted_deliveries=tracker.drain_admitted,
    )
    message = inbound(chat_id="chat", text="draw")
    session_key = build_session_key(message, agent_id="agent-a")
    request = InboundRunRequest(
        routed=RoutedInbound(message=message),
        agent=catalog.require("agent-a"),
        session_key=session_key,
        sender_label="Alice",
    )
    running = asyncio.create_task(coordinator.dispatch(request))
    await kernel.wait_stream("run-1")
    if terminal:
        kernel.finish("run-1")
        await running
    assert store.retained_run_ids(session_key, 0) == ("run-1",)

    if reset_fails:

        def fail(*args, **kwargs):
            raise RuntimeError("publish failed")

        monkeypatch.setattr(binder, "publish_reset", fail)
    reset = await asyncio.wait_for(
        coordinator.new_session(
            NewSessionRequest(
                routed=RoutedInbound(message=inbound(chat_id="chat", text="/new")),
                agent=catalog.require("agent-a"),
                session_key=session_key,
            )
        ),
        timeout=1,
    )
    assert ("未能" in reset.reply_text) is reset_fails
    assert not upload_release.is_set()
    upload_release.set()
    await tracker.drain_run("run-1")
    assert outcomes == [reset_fails]
    if not terminal:
        kernel.finish("run-1")
        await running
    assert store.get("run-1") is None


@pytest.mark.asyncio
async def test_new_waits_for_admitted_request_before_confirming(tmp_path: Path) -> None:
    kernel, catalog, binder, router, _ = build_dependencies(tmp_path)
    store = RunDeliveryContextStore()
    tracker = RuntimeDeliveryTaskTracker(context_store=store)

    async def lifecycle(routed, update) -> None:
        if update.phase == "accepted":
            store.seed_from_lifecycle(
                routed=routed, update=update, owner_user_id="owner"
            )

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        relay_lifecycle_callback=lifecycle,
        delivery_context_store=store,
        drain_admitted_deliveries=tracker.drain_admitted,
    )
    message = inbound(chat_id="chat", text="draw")
    key = build_session_key(message, agent_id="agent-a")
    running = asyncio.create_task(
        coordinator.dispatch(
            InboundRunRequest(
                routed=RoutedInbound(message=message),
                agent=catalog.require("agent-a"),
                session_key=key,
                sender_label="Alice",
            )
        )
    )
    await kernel.wait_stream("run-1")
    assert tracker.admit_publication("run-1")
    reset = asyncio.create_task(
        coordinator.new_session(
            NewSessionRequest(
                routed=RoutedInbound(message=inbound(chat_id="chat", text="/new")),
                agent=catalog.require("agent-a"),
                session_key=key,
            )
        )
    )
    for _ in range(20):
        await asyncio.sleep(0)
        if store.is_quiescing("run-1"):
            break
    assert store.is_quiescing("run-1")
    assert not reset.done()
    assert not tracker.admit_publication("run-1")
    tracker.release_publication("run-1")
    await asyncio.wait_for(reset, timeout=1)
    kernel.finish("run-1")
    await running


@pytest.mark.asyncio
async def test_stop_revokes_upload_before_kernel_terminal_arrives(
    tmp_path: Path,
) -> None:
    kernel, catalog, binder, router, _ = build_dependencies(tmp_path)
    store = RunDeliveryContextStore()
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        delivery_context_store=store,
        relay_lifecycle_callback=build_relay_lifecycle_callback(
            reporter=None,
            im_connection_manager_factory=lambda: None,
            run_context_store=store,
            owner_user_id="owner",
        ),
    )
    message = inbound(chat_id="chat", text="draw")
    key = build_session_key(message, agent_id="agent-a")
    running = asyncio.create_task(
        coordinator.dispatch(
            InboundRunRequest(
                routed=RoutedInbound(message=message),
                agent=catalog.require("agent-a"),
                session_key=key,
                sender_label="Alice",
            )
        )
    )
    await kernel.wait_stream("run-1")
    assert store.retain("run-1")
    await coordinator.stop(
        StopRunRequest(
            routed=RoutedInbound(message=inbound(chat_id="chat", text="/stop")),
            agent=catalog.require("agent-a"),
            session_key=key,
        )
    )
    assert not store.can_publish("run-1")
    kernel.finish("run-1", status="cancelled")
    await running
    assert not store.can_publish("run-1")
    store.release("run-1")
    assert store.get("run-1") is None
