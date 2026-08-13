"""Deterministic interleavings at failed recovery-successor closure."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from personal_assistant.gateway.image_attachments import ImageResolution
from personal_assistant.gateway.inbound_models import InboundRunRequest, RoutedInbound
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from ._session_run_coordinator_helpers import build_dependencies, inbound


class _BlockingImageResolver:
    """Hold one dispatch while it owns the coordinator transition lock."""

    def __init__(self) -> None:
        self.block = False
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def resolve(self, attachments: object) -> ImageResolution:
        del attachments
        if self.block:
            self.entered.set()
            await self.release.wait()
        return ImageResolution(parts=())


def _request(message, catalog) -> InboundRunRequest:  # noqa: ANN001
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        routed=RoutedInbound(message=message),
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


async def _admitted_recovery(tmp_path: Path, resolver: _BlockingImageResolver):  # noqa: ANN202
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
        image_resolver=resolver,
        relay_lifecycle_callback=_capture,
    )
    message = inbound(chat_id="recovery-race", text="primary")
    primary = asyncio.create_task(coordinator.dispatch(_request(message, catalog)))
    await kernel.wait_stream("run-1")
    await coordinator.dispatch(_request(replace(message, text="follow-1"), catalog))
    return coordinator, kernel, catalog, router, message, primary, lifecycle, adopted


def _push_recovery(kernel) -> None:  # noqa: ANN001
    kernel.push("run-1", {"event": "run_status", "status": "failed"})
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
                "pending_ids": ["pending-1"],
            },
        },
    )
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
async def test_lock_held_accepted_follower_is_terminalized_at_failed_successor_close(
    tmp_path: Path,
) -> None:
    resolver = _BlockingImageResolver()
    (
        coordinator,
        kernel,
        catalog,
        router,
        message,
        primary,
        lifecycle,
        adopted,
    ) = await _admitted_recovery(tmp_path, resolver)
    _push_recovery(kernel)
    await asyncio.wait_for(adopted.wait(), timeout=1)
    kernel.forced_active_run_id = "run-2"

    resolver.block = True
    racing = asyncio.create_task(
        coordinator.dispatch(
            _request(replace(message, text="racing follower"), catalog)
        )
    )
    await asyncio.wait_for(resolver.entered.wait(), timeout=1)
    kernel.push("run-1", {"event": "run_status", "run_id": "run-2", "status": "failed"})
    await asyncio.sleep(0)
    resolver.release.set()

    assert (await racing).run_id == "run-2"
    kernel.push(
        "run-1",
        {
            "event": "run_status",
            "run_id": "run-3",
            "status": "queued",
            "continuation": {
                "recovery_id": "recovery-2",
                "predecessor_run_id": "run-2",
                "batch_index": 0,
                "origin": "user",
                "pending_ids": ["pending-2"],
            },
        },
    )
    kernel.push(
        "run-1",
        {
            "event": "recovery_settled",
            "recovery_id": "recovery-2",
            "predecessor_run_id": "run-2",
            "outcome": "scheduled",
            "successor_run_ids": ["run-3"],
        },
    )
    kernel.push(
        "run-1",
        {"event": "assistant_message", "run_id": "run-3", "content": "continued"},
    )
    kernel.push(
        "run-1",
        {"event": "run_status", "run_id": "run-3", "status": "completed"},
    )

    assert (await primary).run_id == "run-3"

    terminal = [
        (text, phase, run_id)
        for text, phase, run_id in lifecycle
        if phase in {"failed", "completed"}
    ]
    assert terminal == [
        ("primary", "failed", "run-1"),
        ("follow-1", "failed", "run-2"),
        ("racing follower", "completed", "run-3"),
    ]
    assert lifecycle.count(("racing follower", "accepted", "run-2")) == 1
    assert lifecycle.count(("racing follower", "completed", "run-3")) == 1
    assert not coordinator.is_session_busy(
        build_session_key(message, agent_id="agent-a")
    )

    later = asyncio.create_task(
        coordinator.dispatch(_request(replace(message, text="ordinary next"), catalog))
    )
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="ordinary reply")
    assert (await later).reply_text == "ordinary reply"
    channel = router._registry.get("web_relay")  # noqa: SLF001
    assert channel is not None
    assert [item.text for item in channel.sent] == ["continued", "ordinary reply"]
