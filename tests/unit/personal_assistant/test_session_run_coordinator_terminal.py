"""Public terminal, liveness, stop, and visibility coordinator behavior."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from agent.sdk import USER_INTERRUPT_RECOVERY_CONTENT

from personal_assistant.gateway.inbound_models import (
    InboundRunRequest,
    RelayLifecycleUpdate,
    StopRunRequest,
)
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from ._session_run_coordinator_helpers import build_dependencies, inbound


def _request(message, catalog) -> InboundRunRequest:
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        message=message,
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
    }
    assert lifecycle[-1].phase == "failed"
    assert not coordinator.is_session_busy(build_session_key(message, agent_id="agent-a"))

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
            message=replace(message, text="/stop"),
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
    }
    assert not coordinator.is_session_busy(request.session_key)
    idle = await coordinator.stop(
        StopRunRequest(
            message=replace(message, text="/stop"),
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
    assert observed[-1]["reason"] == "interrupted"
    assert not coordinator.is_session_busy(build_session_key(message, agent_id="agent-a"))


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
        message = replace(message, metadata={"trigger_source": "feishu"})
    running = asyncio.create_task(coordinator.dispatch(_request(message, catalog)))
    await kernel.wait_stream("run-1")
    kernel.finish("run-1", text="NO_REPLY")

    result = await running
    assert result.reply_text == "NO_REPLY"
    assert result.outbound is None
