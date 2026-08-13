"""Coordinator adoption, closure, and control-race recovery behavior."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from personal_assistant.gateway.inbound_models import (
    InboundRunRequest,
    NewSessionRequest,
    RoutedInbound,
    StopRunRequest,
)
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import (
    RecoveryHandoffError,
    SessionRunCoordinator,
)

from ._session_run_coordinator_helpers import build_dependencies, inbound


def _request(message, catalog) -> InboundRunRequest:  # noqa: ANN001
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        routed=RoutedInbound(message=message),
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


async def _admitted_recovery(tmp_path: Path, *, follower_count: int = 1):  # noqa: ANN202
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    kernel.inject_steer = True
    lifecycle: list[tuple[str, str, str | None]] = []
    adopted = asyncio.Event()

    async def _capture(message, update) -> None:  # noqa: ANN001
        lifecycle.append((message.message.text, update.phase, update.run_id))
        if update.phase == "recovery_adopted":
            adopted.set()

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        relay_lifecycle_callback=_capture,
    )
    message = inbound(chat_id="recovery", text="primary")
    primary = asyncio.create_task(coordinator.dispatch(_request(message, catalog)))
    await kernel.wait_stream("run-1")
    for index in range(follower_count):
        await coordinator.dispatch(
            _request(replace(message, text=f"follow-{index + 1}"), catalog)
        )
    return coordinator, kernel, catalog, router, message, primary, lifecycle, adopted


def _push_old_terminal(kernel) -> None:  # noqa: ANN001
    kernel.push("run-1", {"event": "run_status", "status": "failed"})


def _push_successor(kernel, *, pending_ids: list[str]) -> None:  # noqa: ANN001
    kernel.push(
        "run-1",
        {
            "event": "run_status",
            "run_id": "run-2",
            "status": "queued",
            "continuation": {
                "recovery_id": "recovery-1",
                "predecessor_run_id": "run-1",
                "batch_index": 0,
                "origin": "user",
                "pending_ids": pending_ids,
            },
        },
    )


def _push_settlement(kernel) -> None:  # noqa: ANN001
    kernel.push(
        "run-1",
        {
            "event": "recovery_settled",
            "recovery_id": "recovery-1",
            "predecessor_run_id": "run-1",
            "outcome": "scheduled",
            "successor_run_ids": ["run-2"],
        },
    )


@pytest.mark.asyncio
async def test_correlated_successor_delivers_once_and_terminalizes_all_followers(
    tmp_path: Path,
) -> None:
    _, kernel, _, router, _, primary, lifecycle, _ = await _admitted_recovery(
        tmp_path, follower_count=2
    )
    _push_old_terminal(kernel)
    _push_successor(kernel, pending_ids=["pending-1", "pending-2"])
    _push_settlement(kernel)
    kernel.push(
        "run-1",
        {"event": "assistant_message", "run_id": "run-2", "content": "continued"},
    )
    kernel.push(
        "run-1", {"event": "run_status", "run_id": "run-2", "status": "completed"}
    )

    assert (await primary).run_id == "run-2"
    channel = router._registry.get("web_relay")  # noqa: SLF001
    assert channel is not None
    assert [item.text for item in channel.sent] == ["continued"]
    assert lifecycle[-4:] == [
        ("follow-1", "recovery_adopted", "run-2"),
        ("follow-1", "running", "run-2"),
        ("follow-1", "completed", "run-2"),
        ("follow-2", "completed", "run-2"),
    ]


@pytest.mark.asyncio
async def test_consumed_prefix_fails_while_unconsumed_suffix_is_adopted(
    tmp_path: Path,
) -> None:
    _, kernel, _, _, _, primary, lifecycle, _ = await _admitted_recovery(
        tmp_path, follower_count=2
    )
    kernel.push("run-1", {"event": "injection_consumed", "user_message_count": 1})
    _push_old_terminal(kernel)
    _push_successor(kernel, pending_ids=["pending-2"])
    _push_settlement(kernel)
    kernel.push(
        "run-1", {"event": "run_status", "run_id": "run-2", "status": "completed"}
    )

    await primary
    terminal = [
        (text, phase)
        for text, phase, _ in lifecycle
        if phase in {"failed", "completed"}
    ]
    assert terminal == [
        ("primary", "failed"),
        ("follow-1", "failed"),
        ("follow-2", "completed"),
    ]


@pytest.mark.asyncio
async def test_corrupt_handoff_fails_once_and_releases_session(tmp_path: Path) -> None:
    (
        coordinator,
        kernel,
        _,
        _,
        message,
        primary,
        lifecycle,
        _,
    ) = await _admitted_recovery(tmp_path)
    _push_old_terminal(kernel)
    _push_successor(kernel, pending_ids=["wrong"])

    with pytest.raises(RecoveryHandoffError, match="pending ids"):
        await primary
    assert [(text, phase) for text, phase, _ in lifecycle if phase == "failed"] == [
        ("primary", "failed"),
        ("follow-1", "failed"),
    ]
    assert not coordinator.is_session_busy(
        build_session_key(message, agent_id="agent-a")
    )


@pytest.mark.asyncio
async def test_new_message_during_adopted_successor_stays_same_run(
    tmp_path: Path,
) -> None:
    (
        coordinator,
        kernel,
        catalog,
        _,
        message,
        primary,
        lifecycle,
        adopted,
    ) = await _admitted_recovery(tmp_path)
    _push_old_terminal(kernel)
    _push_successor(kernel, pending_ids=["pending-1"])
    _push_settlement(kernel)
    await asyncio.wait_for(adopted.wait(), timeout=1)
    kernel.forced_active_run_id = "run-2"

    later = await coordinator.dispatch(
        _request(replace(message, text="later steer"), catalog)
    )
    assert later.run_id == "run-2"
    kernel.push(
        "run-1",
        {
            "event": "injection_consumed",
            "run_id": "run-2",
            "user_message_count": 1,
        },
    )
    kernel.push(
        "run-1", {"event": "run_status", "run_id": "run-2", "status": "completed"}
    )

    await primary
    assert ("later steer", "accepted", "run-2") in lifecycle
    assert ("later steer", "completed", "run-2") in lifecycle


@pytest.mark.asyncio
@pytest.mark.parametrize("control", ["stop", "new"])
async def test_control_after_adoption_fences_recovery_output(
    tmp_path: Path, control: str
) -> None:
    (
        coordinator,
        kernel,
        catalog,
        router,
        message,
        primary,
        lifecycle,
        adopted,
    ) = await _admitted_recovery(tmp_path)
    _push_old_terminal(kernel)
    _push_successor(kernel, pending_ids=["pending-1"])
    await asyncio.wait_for(adopted.wait(), timeout=1)
    request = _request(message, catalog)
    routed = RoutedInbound(message=replace(message, text=f"/{control}"))
    if control == "stop":
        result = await coordinator.stop(
            StopRunRequest(
                routed=routed, agent=request.agent, session_key=request.session_key
            )
        )
    else:
        result = await coordinator.new_session(
            NewSessionRequest(
                routed=routed,
                agent=request.agent,
                session_key=request.session_key,
                operation_id="new-1",
            )
        )
    completed = await primary
    channel = router._registry.get("web_relay")  # noqa: SLF001
    assert completed.outbound is None
    assert channel is not None
    assert [item.text for item in channel.sent] == [result.reply_text]
    assert ("follow-1", "completed", "run-2") in lifecycle
    assert kernel.cancel_calls == ["run-2"]


@pytest.mark.asyncio
async def test_shutdown_during_recovery_fails_each_accepted_message_once(
    tmp_path: Path,
) -> None:
    (
        coordinator,
        kernel,
        _,
        _,
        _,
        primary,
        lifecycle,
        adopted,
    ) = await _admitted_recovery(tmp_path)
    _push_old_terminal(kernel)
    _push_successor(kernel, pending_ids=["pending-1"])
    await asyncio.wait_for(adopted.wait(), timeout=1)

    coordinator.seal()
    with pytest.raises(RuntimeError, match="queue"):
        await coordinator.drain(asyncio.get_running_loop().time())
    with pytest.raises(asyncio.CancelledError):
        await primary
    assert [(text, phase) for text, phase, _ in lifecycle if phase == "failed"] == [
        ("primary", "failed"),
        ("follow-1", "failed"),
    ]
    assert kernel.cancel_calls == ["run-2"]
