"""Public terminal, liveness, stop, and visibility coordinator behavior."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from agent.sdk import USER_INTERRUPT_RECOVERY_CONTENT

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    InboundIngress,
)
from personal_assistant.gateway.inbound_models import (
    InboundRunRequest,
    RelayLifecycleUpdate,
    RoutedInbound,
    StopRunRequest,
)
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.runtime_footer import ExternalFinalProjection
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from ._pipeline_helpers import _FakeChannel
from ._session_run_coordinator_helpers import build_dependencies, inbound


def _request(message, catalog) -> InboundRunRequest:
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        routed=RoutedInbound(message=message),
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


@pytest.mark.asyncio
async def test_quiet_run_heartbeats_prevent_idle_reap(tmp_path: Path) -> None:
    """Periodic liveness keeps an otherwise silent run alive past one idle window."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        run_idle_timeout_seconds=0.04,
    )
    running = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="quiet", text="work"), catalog))
    )
    await kernel.wait_stream("run-1")

    # The 25ms cadence is intentionally below the configured 40ms watchdog window;
    # three events keep the run alive for longer than one full window.
    for _ in range(3):
        await asyncio.sleep(0.025)
        kernel.push("run-1", {"event": "run_heartbeat", "source": "tool"})
    kernel.finish("run-1", text="quiet done")

    assert (await running).reply_text == "quiet done"
    assert kernel.cancel_calls == []


@pytest.mark.asyncio
async def test_permission_wait_suspends_then_resolved_restores_idle_watchdog(
    tmp_path: Path,
) -> None:
    """Human decision time is exempt; post-decision silence is a real stall."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    pending_seen = asyncio.Event()
    resolved_seen = asyncio.Event()

    async def _observe(event) -> None:
        if event.get("event") == "permission_request":
            pending_seen.set()
        elif event.get("event") == "permission_resolved":
            resolved_seen.set()

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        kernel_event_observer=_observe,
        run_idle_timeout_seconds=0.02,
    )
    running = asyncio.create_task(
        coordinator.dispatch(
            _request(inbound(chat_id="permission", text="protected work"), catalog)
        )
    )
    await kernel.wait_stream("run-1")
    kernel.push("run-1", {"event": "permission_request", "request_id": "perm-1"})
    await asyncio.wait_for(pending_seen.wait(), timeout=1)

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(asyncio.shield(running), timeout=0.06)
    assert not running.done()
    assert kernel.cancel_calls == []

    kernel.push("run-1", {"event": "permission_resolved", "request_id": "perm-1"})
    await asyncio.wait_for(resolved_seen.wait(), timeout=1)
    with pytest.raises(TimeoutError, match="produced no events"):
        await running
    assert kernel.cancel_calls == ["run-1"]


@pytest.mark.asyncio
async def test_real_stall_fails_and_releases_next_same_session_turn(
    tmp_path: Path,
) -> None:
    """Lost liveness cancels/reconciles/fails once, then the FIFO can continue."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    reconciles: list[dict[str, object]] = []
    lifecycle: list[RelayLifecycleUpdate] = []

    async def _capture(_message, update) -> None:
        lifecycle.append(update)

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        run_idle_timeout_seconds=0.02,
        kernel_event_observer=lambda event: reconciles.append(dict(event)),
        relay_lifecycle_callback=_capture,
    )
    message = inbound(chat_id="stall", text="first")

    with pytest.raises(TimeoutError, match="produced no events"):
        await coordinator.dispatch(_request(message, catalog))

    assert kernel.cancel_calls == ["run-1"]
    assert reconciles[-1] == {
        "event": "run_terminal_reconcile",
        "run_id": "run-1",
        "reason": "stalled",
        "finalize_bubble": True,
        "delivery_status": "failed",
    }
    assert lifecycle[-1].phase == "failed"
    assert not coordinator.is_session_busy(
        build_session_key(message, agent_id="agent-a")
    )

    next_turn = asyncio.create_task(
        coordinator.dispatch(_request(replace(message, text="second"), catalog))
    )
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="recovered")
    assert (await next_turn).reply_text == "recovered"


@pytest.mark.asyncio
async def test_user_stop_reconciles_on_original_consumer_and_cleans_marker(
    tmp_path: Path,
) -> None:
    """Stop attribution survives until original stream reconcile, then is cleared."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    observed: list[dict[str, object]] = []
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        kernel_event_observer=lambda event: observed.append(dict(event)),
    )
    message = inbound(chat_id="stop", text="work")
    request = _request(message, catalog)
    running = asyncio.create_task(coordinator.dispatch(request))
    await kernel.wait_stream("run-1")

    stopped = await coordinator.stop(
        StopRunRequest(
            routed=RoutedInbound(message=replace(message, text="/stop")),
            agent=request.agent,
            session_key=request.session_key,
        )
    )
    kernel.finish("run-1", status="cancelled", text="")
    completed = await running

    assert stopped.reply_text == "已停止当前操作。"
    assert completed.outbound is None
    assert observed[-1] == {
        "event": "run_terminal_reconcile",
        "run_id": "run-1",
        "reason": "interrupted",
        "content": USER_INTERRUPT_RECOVERY_CONTENT,
        "finalize_bubble": True,
        "delivery_status": "completed",
    }
    assert not coordinator.is_session_busy(request.session_key)
    idle = await coordinator.stop(
        StopRunRequest(
            routed=RoutedInbound(message=replace(message, text="/stop")),
            agent=request.agent,
            session_key=request.session_key,
        )
    )
    assert idle.reply_text == "当前没有正在执行的操作。"


@pytest.mark.asyncio
async def test_terminal_failure_reconciles_fails_lifecycle_and_cleans_state(
    tmp_path: Path,
) -> None:
    """A failed terminal cannot leave active or interrupt state behind."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    observed: list[dict[str, object]] = []
    lifecycle: list[RelayLifecycleUpdate] = []

    async def _capture(_message, update) -> None:
        lifecycle.append(update)

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        kernel_event_observer=lambda event: observed.append(dict(event)),
        relay_lifecycle_callback=_capture,
    )
    message = inbound(chat_id="failed", text="work")
    failed = asyncio.create_task(coordinator.dispatch(_request(message, catalog)))
    await kernel.wait_stream("run-1")
    kernel.finish("run-1", status="failed", text="")

    with pytest.raises(RuntimeError, match="status=failed"):
        await failed
    assert lifecycle[-1].phase == "failed"
    assert observed[-1] == {
        "event": "run_terminal_reconcile",
        "run_id": "run-1",
        "reason": "interrupted",
        "finalize_bubble": True,
        "delivery_status": "failed",
    }
    assert not coordinator.is_session_busy(
        build_session_key(message, agent_id="agent-a")
    )


@pytest.mark.asyncio
async def test_completed_foreground_run_survives_background_subscription_seal(
    tmp_path: Path,
) -> None:
    """Optional background admission cannot turn a completed foreground run failed."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    lifecycle: list[str] = []

    async def _capture(_message, update: RelayLifecycleUpdate) -> None:
        lifecycle.append(update.phase)

    background_subscriptions = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=lambda _context, _agent, _session, _event: asyncio.sleep(
            0
        ),
    )
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        background_subscriptions=background_subscriptions,
        relay_lifecycle_callback=_capture,
    )
    running = asyncio.create_task(
        coordinator.dispatch(
            _request(inbound(chat_id="sealed-background", text="work"), catalog)
        )
    )
    await kernel.wait_stream("run-1")

    background_subscriptions.seal()
    kernel.finish("run-1", text="completed before shutdown")

    result = await running
    assert result.reply_text == "completed before shutdown"
    assert lifecycle == ["accepted", "running", "completed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("external", [False, True])
async def test_no_reply_never_reaches_group_or_external_target(
    tmp_path: Path, external: bool
) -> None:
    """Protocol silence remains invisible at both guarded delivery boundaries."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    message = inbound(chat_id=f"silent-{external}", text="work", is_group=not external)
    if external:
        message = replace(
            message,
            ingress=InboundIngress(
                external_conversation=ExternalConversationIdentity(
                    external_source="feishu",
                    external_chat_id="feishu:app:dm:user-1",
                    agent_id="agent-a",
                    conversation_type="direct",
                    trigger_source="feishu",
                )
            ),
        )
    running = asyncio.create_task(coordinator.dispatch(_request(message, catalog)))
    await kernel.wait_stream("run-1")
    kernel.finish("run-1", text="NO_REPLY")

    result = await running
    assert result.reply_text == "NO_REPLY"
    assert result.outbound is None


@pytest.mark.asyncio
async def test_external_final_fallback_reuses_observer_footer_projection(
    tmp_path: Path,
) -> None:
    """The direct terminal fallback sends the observer's exact cached projection."""

    kernel, catalog, binder, _router, group_store = build_dependencies(tmp_path)
    feishu = _FakeChannel("feishu:agent-a")
    router = OutboundRouter(ChannelRegistry((feishu,)))
    lifecycle: list[RelayLifecycleUpdate] = []

    async def _capture(_routed, update: RelayLifecycleUpdate) -> None:
        lifecycle.append(update)

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        external_final_projection_provider=lambda run_id: (
            ExternalFinalProjection(
                text="done",
                runtime_footer="gpt-5.4 · ctx 42%",
            )
            if run_id == "run-1"
            else None
        ),
        relay_lifecycle_callback=_capture,
    )
    message = replace(
        inbound(chat_id="external-fallback", text="work"),
        channel_name="feishu:agent-a",
        ingress=InboundIngress(
            external_conversation=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="feishu:app:dm:user-1",
                agent_id="agent-a",
                conversation_type="direct",
                trigger_source="feishu",
            )
        ),
    )

    running = asyncio.create_task(coordinator.dispatch(_request(message, catalog)))
    await kernel.wait_stream("run-1")
    kernel.finish("run-1", text="done")

    result = await running
    assert result.reply_text == "done"
    assert [outbound.text for outbound in feishu.sent] == ["done"]
    assert feishu.sent[0].metadata["runtime_footer"] == "gpt-5.4 · ctx 42%"
    assert feishu.sent[0].metadata["reply_phase"] == "final"
    assert lifecycle[0].model == "test-model"


@pytest.mark.asyncio
async def test_shutdown_fails_primary_and_steered_accepted_messages(
    tmp_path: Path,
) -> None:
    """Every accepted relay item reaches terminal when its shared run is cancelled."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    kernel.inject_steer = True
    lifecycle: list[tuple[str, str]] = []

    async def _capture(message, update) -> None:
        lifecycle.append((message.message.text, update.phase))

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        relay_lifecycle_callback=_capture,
    )
    primary_message = inbound(chat_id="shutdown", text="primary")
    primary = asyncio.create_task(
        coordinator.dispatch(_request(primary_message, catalog))
    )
    await kernel.wait_stream("run-1")

    steered_message = inbound(chat_id="shutdown", text="steered")
    steered = await coordinator.dispatch(_request(steered_message, catalog))
    assert steered.run_id == "run-1"

    coordinator.seal()
    with pytest.raises(RuntimeError, match="queue"):
        await coordinator.drain(asyncio.get_running_loop().time())
    with pytest.raises(asyncio.CancelledError):
        await primary

    assert lifecycle == [
        ("primary", "accepted"),
        ("steered", "accepted"),
        ("primary", "failed"),
        ("steered", "failed"),
    ]
