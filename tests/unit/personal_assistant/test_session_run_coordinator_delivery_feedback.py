"""Delivery repair keeps ordinary session admission and logical request ownership."""

import asyncio
from dataclasses import replace

import pytest

from agent.core.agent.state import parse_input_parts
from agent.core.agent.message_context import input_context_metadata
from personal_assistant.gateway.delivery_feedback import feedback_parts
from personal_assistant.gateway.inbound_models import (
    InboundRunRequest,
    NewSessionRequest,
    RoutedInbound,
    StopRunRequest,
)
from personal_assistant.gateway.runtime_delivery.context import (
    RunDeliveryContext,
    RunDeliveryContextStore,
    RunDeliveryTarget,
)
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from ._session_run_coordinator_helpers import build_dependencies, inbound


class Budget:
    def __init__(self):
        self.admitted = []

    def next_submission(self, logical_id):
        ordinal = len(self.admitted) + 1
        return (f"{logical_id}:feedback:{ordinal}", ordinal) if ordinal <= 2 else None

    def record_admitted(self, logical_id, submission_id):
        self.admitted.append((logical_id, submission_id))


def setup(tmp_path, *, busy=False):
    kernel, catalog, binder, router, _ = build_dependencies(tmp_path)
    contexts = RunDeliveryContextStore()
    budget = Budget()
    lifecycle = []
    admissions = []
    request = InboundRunRequest(
        routed=RoutedInbound(message=inbound(chat_id="repair", text="show image")),
        agent=catalog.require("agent-a"),
        session_key=build_session_key(
            inbound(chat_id="repair", text="show image"), agent_id="agent-a"
        ),
        sender_label="Alice",
    )

    async def on_lifecycle(routed, update):
        lifecycle.append(update)
        if update.phase == "accepted":
            contexts.seed(
                RunDeliveryContext(
                    run_id=update.run_id,
                    agent_id=update.agent_id,
                    kernel_session_id=update.kernel_session_id,
                    delivery_target=RunDeliveryTarget.none(),
                    model=update.model or "test-model",
                )
            )

    async def observe(event):
        if event["event"] != "assistant_message":
            return
        context = contexts.get(event["run_id"])
        context.delivery_candidate_seen = True
        if event["content"] == "private image":
            context.delivery_failed = True
            context.delivery_feedback = (
                "<system-reminder>This reply was not delivered.</system-reminder>"
            )
        else:
            context.delivery_published_text = event["content"]

    def admit(**kwargs):
        admissions.append(kwargs)
        return None if busy else kernel.submit(**kwargs)

    kernel.try_submit_idle = admit
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        relay_lifecycle_callback=on_lifecycle,
        kernel_event_observer=observe,
        delivery_context_store=contexts,
        delivery_feedback_budget=budget,
    )
    return coordinator, kernel, request, budget, lifecycle, admissions


def test_feedback_is_parsed_as_system_input():
    parts = parse_input_parts(feedback_parts("image unavailable", 1))
    assert parts[0].metadata["context_origin"] == "system"
    metadata = input_context_metadata(parts, origin="user", metadata={})
    assert metadata["context_origin"] == "system"
    assert not metadata.get("context_has_human", False)


@pytest.mark.asyncio
async def test_private_failure_repairs_twice_then_fails_without_raw_fallback(tmp_path):
    coordinator, kernel, request, budget, lifecycle, admissions = setup(tmp_path)
    task = asyncio.create_task(coordinator.dispatch(request))
    for run_id in ("run-1", "run-2", "run-3"):
        await kernel.wait_stream(run_id)
        kernel.finish(run_id, text="private image")
    result = await task
    assert result.reply_text == ""
    assert result.outbound is None
    assert len(admissions) == 2
    assert [entry[0] for entry in budget.admitted] == ["run-1", "run-1"]
    assert (
        admissions[0]["session_id"]
        == admissions[1]["session_id"]
        == result.kernel_session_id
    )
    assert "plain text" not in admissions[0]["parts"][0]["text"]
    assert "plain text" in admissions[1]["parts"][0]["text"]
    assert lifecycle[-1].phase == "failed"
    assert not coordinator.is_session_busy(request.session_key)


@pytest.mark.asyncio
async def test_repair_success_completes_original_request(tmp_path):
    coordinator, kernel, request, budget, lifecycle, _ = setup(tmp_path)
    task = asyncio.create_task(coordinator.dispatch(request))
    await kernel.wait_stream("run-1")
    kernel.finish("run-1", text="private image")
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="Image unavailable; here is the explanation.")
    result = await task
    assert result.reply_text == "Image unavailable; here is the explanation."
    assert len(budget.admitted) == 1
    assert lifecycle[-1].phase == "completed"


@pytest.mark.asyncio
async def test_busy_admission_does_not_consume_budget(tmp_path):
    coordinator, kernel, request, budget, lifecycle, admissions = setup(
        tmp_path, busy=True
    )
    task = asyncio.create_task(coordinator.dispatch(request))
    await kernel.wait_stream("run-1")
    kernel.finish("run-1", text="private image")
    assert (await task).outbound is None
    assert len(admissions) == 1
    assert budget.admitted == []
    assert lifecycle[-1].phase == "failed"


@pytest.mark.asyncio
async def test_new_input_wins_over_pending_private_repair(tmp_path):
    coordinator, kernel, request, budget, _, admissions = setup(tmp_path)
    task = asyncio.create_task(coordinator.dispatch(request))
    await kernel.wait_stream("run-1")
    kernel.inject_steer = True
    await coordinator.dispatch(
        replace(
            request,
            routed=RoutedInbound(message=replace(request.message, text="new question")),
        )
    )
    kernel.finish("run-1", text="private image")
    await task
    assert admissions == []
    assert budget.admitted == []


@pytest.mark.asyncio
@pytest.mark.parametrize("control", ["stop", "new_session"])
async def test_control_discards_pending_private_repair(tmp_path, control):
    coordinator, kernel, request, budget, _, admissions = setup(tmp_path)
    task = asyncio.create_task(coordinator.dispatch(request))
    await kernel.wait_stream("run-1")
    kernel.push("run-1", {"event": "assistant_message", "content": "private image"})
    command = NewSessionRequest if control == "new_session" else StopRunRequest
    await getattr(coordinator, control)(
        command(
            routed=request.routed, agent=request.agent, session_key=request.session_key
        )
    )
    kernel.finish(
        "run-1",
        status="completed" if control == "new_session" else "cancelled",
        text="",
    )
    await task
    assert admissions == []
    assert budget.admitted == []


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_unattended_feedback_preserves_owner_route_and_budget(
    tmp_path, repair_succeeds
):
    from personal_assistant.gateway.runtime_delivery.stream import (
        stream_run_to_completion,
    )

    _, kernel, request, budget, _, _ = setup(tmp_path)
    # Stream owner receives the same SDK-style idle seam, with the real workspace
    # frozen by heartbeat/cron before entering the shared stream coordinator.
    contexts = RunDeliveryContextStore()
    routed = []

    def observer(event):
        context = contexts.get(event["run_id"])
        if event["event"] == "assistant_message":
            routed.append(context.owner_user_id)
            context.delivery_candidate_seen = True
            if event["content"] == "private image":
                context.delivery_failed = True
                context.delivery_feedback = "This candidate was never sent."
            else:
                context.delivery_published_text = event["content"]

    kernel.submit(session_id="scheduled-session", parts=[])
    task = asyncio.create_task(
        stream_run_to_completion(
            run_id="run-1",
            kernel_session_id="scheduled-session",
            agent_id="agent-a",
            owner_user_id="owner-a",
            kernel=kernel,
            run_context_store=contexts,
            observer=observer,
            delivery_feedback_budget=budget,
            workspace_root=request.agent.config.workspace_root,
        )
    )
    await kernel.wait_stream("run-1")
    kernel.finish("run-1", text="private image")
    await kernel.wait_stream("run-2")
    kernel.finish(
        "run-2", text="Delivered text" if repair_succeeds else "private image"
    )
    if not repair_succeeds:
        await kernel.wait_stream("run-3")
        kernel.finish("run-3", text="private image")
    outcome = await task
    assert outcome.status == ("completed" if repair_succeeds else "failed")
    assert outcome.final_text == ("Delivered text" if repair_succeeds else "")
    assert routed == ["owner-a"] * (2 if repair_succeeds else 3)
    assert {logical_id for logical_id, _ in budget.admitted} == {"run-1"}
    assert all(contexts.get(run_id) is None for run_id in ("run-1", "run-2", "run-3"))
