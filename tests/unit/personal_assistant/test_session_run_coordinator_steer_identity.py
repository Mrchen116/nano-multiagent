"""Run-identity guarantees for SessionRunCoordinator steer admission."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.gateway.inbound_models import InboundRunRequest, RoutedInbound
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

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
async def test_replaced_kernel_run_gets_no_follower_and_falls_back_once(
    tmp_path: Path,
) -> None:
    """A coordinator marker for A cannot steer or register a follower on B."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    first_message = inbound(chat_id="chat-a", text="first")
    first = asyncio.create_task(coordinator.dispatch(_request(first_message, catalog)))
    await kernel.wait_stream("run-1")
    kernel.inject_steer = True
    kernel.forced_active_run_id = "replacement-run-b"

    follower = asyncio.create_task(
        coordinator.dispatch(
            _request(inbound(chat_id="chat-a", text="follower"), catalog)
        )
    )
    await kernel.wait_try_steer_count(1)

    assert kernel.try_steer_calls[-1]["expected_run_id"] == "run-1"
    assert not follower.done()
    kernel.finish("run-1", text="first done")
    assert (await first).run_id == "run-1"
    kernel.forced_active_run_id = None
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="fallback done")

    result = await follower
    assert result.run_id == "run-2"
    assert [call["run_id"] for call in kernel.submit_calls if not call["steer"]] == [
        "run-1",
        "run-2",
    ]


@pytest.mark.asyncio
async def test_native_group_admission_and_consumption_retain_exact_sources(
    tmp_path: Path,
) -> None:
    from dataclasses import replace
    from personal_assistant.channels.base import IMRelayIngress, InboundIngress

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    observed = []
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        kernel_event_observer=observed.append,
    )

    def group(text, message_id):
        return replace(
            inbound(chat_id="group-a", text=text),
            is_group=True,
            ingress=InboundIngress(
                im_relay=IMRelayIngress(
                    relay_task_id=message_id,
                    idempotency_key=message_id,
                    im_message_id=message_id,
                )
            ),
        )

    first = asyncio.create_task(
        coordinator.dispatch(_request(group("first", "input-1"), catalog))
    )
    await kernel.wait_stream("run-1")
    assert kernel.submit_calls[0]["revalidate_output"] is True
    kernel.inject_steer = True
    await coordinator.dispatch(_request(group("second", "input-2"), catalog))
    await coordinator.dispatch(_request(group("third", "input-3"), catalog))
    # A task notification shares the queue but has no human source reference.
    kernel.push(
        "run-1",
        {
            "event": "injection_consumed",
            "run_id": "run-1",
            "pending_ids": ["background-pending", "pending-1", "pending-2"],
            "context_revision": 3,
            "message_count": 3,
        },
    )
    kernel.finish("run-1", text="done")
    await first
    consumed = next(e for e in observed if e["event"] == "injection_consumed")
    assert [x["message_id"] for x in consumed["source_messages"]] == [
        "input-2",
        "input-3",
    ]
    assert [x["sender"] for x in consumed["source_messages"]] == ["Alice", "Alice"]


@pytest.mark.asyncio
async def test_direct_admission_keeps_output_revalidation_disabled(
    tmp_path: Path,
) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    run = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="direct", text="hello"), catalog))
    )
    await kernel.wait_stream("run-1")
    kernel.finish("run-1", text="hello")
    await run
    assert kernel.submit_calls[0]["revalidate_output"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal_status, expected_phase",
    [("completed", "completed"), ("failed", "failed")],
)
async def test_background_group_run_accepts_steer_and_enriches_process(
    tmp_path: Path,
    terminal_status: str,
    expected_phase: str,
) -> None:
    from dataclasses import replace
    from personal_assistant.channels.base import (
        IMRelayIngress,
        InboundIngress,
        ReplyContext,
    )
    from personal_assistant.gateway.session_keys import SessionBinding

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    observed = []
    lifecycle = []

    async def capture(message, update):
        lifecycle.append((message.message.text, update.phase, update.run_id))

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        kernel_event_observer=observed.append,
        relay_lifecycle_callback=capture,
    )
    message = replace(
        inbound(chat_id="group-bg", text="Use Tuesday", is_group=True),
        ingress=InboundIngress(
            im_relay=IMRelayIngress(
                relay_task_id="task-human",
                idempotency_key="human-2",
                im_message_id="human-2",
            )
        ),
    )
    request = _request(message, catalog)
    binding = SessionBinding(
        session_key=request.session_key,
        kernel_session_id="session-bg",
        reply_context=ReplyContext(channel_name="web_relay", target_chat_id="group-bg"),
    )

    async def emit(**event):
        return await coordinator.observe_background_run(
            binding=binding, agent=request.agent, event={"run_id": "bg-1", **event}
        )

    assert not await emit(
        event="run_status",
        status="running",
        origin="background_task",
        revalidate_output=False,
    )
    assert await emit(
        event="run_status",
        status="running",
        origin="background_task",
        revalidate_output=True,
    )
    kernel.inject_steer = True
    kernel.forced_active_run_id = "bg-1"
    accepted = await coordinator.dispatch(request)
    assert accepted.run_id == "bg-1"
    assert all(call["steer"] for call in kernel.submit_calls)
    assert await emit(event="draft_withheld", text="Use Monday")
    assert await emit(
        event="injection_consumed", pending_ids=["pending-1"], context_revision=1
    )
    assert observed[-1]["source_messages"][0]["message_id"] == "human-2"
    assert await emit(event="run_status", status=terminal_status)
    assert not await emit(event="assistant_message", content="duplicate after terminal")
    assert lifecycle[-1] == ("Use Tuesday", expected_phase, "bg-1")


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["failed", "completed"])
async def test_background_unconsumed_steer_uses_existing_recovery_and_completes_once(
    tmp_path: Path,
    terminal_status: str,
) -> None:
    from dataclasses import replace
    from personal_assistant.channels.base import ReplyContext
    from personal_assistant.gateway.session_keys import SessionBinding
    from .test_recovery_handoff_coordinator import _push_settlement, _push_successor

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    lifecycle = []
    observed = []

    async def capture(message, update):
        lifecycle.append((message.message.text, update.phase, update.run_id))

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        relay_lifecycle_callback=capture,
        kernel_event_observer=observed.append,
    )
    request = _request(
        inbound(chat_id="group-bg", text="already consumed", is_group=True), catalog
    )
    binding = SessionBinding(
        session_key=request.session_key,
        kernel_session_id="session-bg",
        reply_context=ReplyContext(channel_name="web_relay", target_chat_id="group-bg"),
    )
    kernel.submit(
        session_id="session-bg", parts=[{"type": "text", "text": "task result"}]
    )

    async def emit(**event):
        return await coordinator.observe_background_run(
            binding=binding, agent=request.agent, event={"run_id": "run-1", **event}
        )

    await emit(
        event="run_status",
        status="running",
        origin="background_task",
        revalidate_output=True,
    )
    kernel.inject_steer = True
    await coordinator.dispatch(request)
    await emit(
        event="injection_consumed", pending_ids=["pending-1"], context_revision=1
    )
    await coordinator.dispatch(
        replace(
            request,
            routed=RoutedInbound(
                message=replace(request.routed.message, text="must survive")
            ),
        )
    )
    terminal = asyncio.create_task(
        emit(
            event="run_status",
            status=terminal_status,
            stop_reason="max_turns_reached"
            if terminal_status == "completed"
            else "error",
            _id=10,
        )
    )
    await kernel.wait_stream("run-1")
    _push_successor(kernel, pending_ids=["pending-2"])
    _push_settlement(kernel)
    kernel.push(
        "run-1",
        {"event": "assistant_message", "run_id": "run-2", "content": "corrected"},
    )
    kernel.push(
        "run-1", {"event": "run_status", "run_id": "run-2", "status": "completed"}
    )
    assert await asyncio.wait_for(terminal, timeout=2)

    assert lifecycle.count(("already consumed", "failed", "run-1")) == 1
    assert lifecycle.count(("must survive", "recovery_adopted", "run-2")) == 1
    assert lifecycle.count(("must survive", "completed", "run-2")) == 1
    assert not any(
        text == "must survive" and phase == "failed" for text, phase, _ in lifecycle
    )
    assert [e["content"] for e in observed if e["event"] == "assistant_message"] == [
        "corrected"
    ]
    assert not await emit(event="assistant_message", content="late duplicate")
