"""Public admission and linearization behavior of SessionRunCoordinator."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.inbound_models import (
    InboundRunRequest,
    StopRunRequest,
)
from personal_assistant.gateway.image_attachments import ImageResolution
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from ._session_run_coordinator_helpers import (
    CountingImageResolver,
    build_dependencies,
    inbound,
)


def _request(message, catalog) -> InboundRunRequest:
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        message=message,
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


class _GatedImageResolver:
    """Expose successive pre-submit resolution gates without timing sleeps."""

    def __init__(self, count: int) -> None:
        self.entered = tuple(asyncio.Event() for _ in range(count))
        self.release = tuple(asyncio.Event() for _ in range(count))
        self._calls = 0

    async def resolve(self, attachments: object) -> ImageResolution:
        del attachments
        index = self._calls
        self._calls += 1
        self.entered[index].set()
        await self.release[index].wait()
        return ImageResolution(parts=())


@pytest.mark.asyncio
async def test_fallback_serializes_same_session_while_other_session_runs(
    tmp_path: Path,
) -> None:
    """A lost steer falls into FIFO once, without blocking another session."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    first_message = inbound(chat_id="chat-a", text="first")
    second_message = inbound(chat_id="chat-a", text="second")
    other_message = inbound(chat_id="chat-b", text="other")

    first = asyncio.create_task(coordinator.dispatch(_request(first_message, catalog)))
    await kernel.wait_stream("run-1")
    second = asyncio.create_task(
        coordinator.dispatch(_request(second_message, catalog))
    )
    await kernel.wait_submit_count(2)
    other = asyncio.create_task(coordinator.dispatch(_request(other_message, catalog)))
    await kernel.wait_stream("run-2")

    assert coordinator.is_session_busy(
        build_session_key(first_message, agent_id="agent-a")
    )
    assert not second.done()
    kernel.finish("run-1", text="first done")
    await first
    await kernel.wait_stream("run-3")
    kernel.finish("run-2", text="other done")
    kernel.finish("run-3", text="second done")

    assert (await other).reply_text == "other done"
    assert (await second).reply_text == "second done"


@pytest.mark.asyncio
async def test_fallback_uses_inject_only_sdk_before_single_normal_submit(
    tmp_path: Path,
) -> None:
    """A lost steer owns no run; FIFO creates exactly one fallback after terminal."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    first = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="one"), catalog))
    )
    await kernel.wait_stream("run-1")
    second = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="two"), catalog))
    )

    await kernel.wait_try_steer_count(1)
    assert [call for call in kernel.submit_calls if not call["steer"]] == [
        kernel.submit_calls[0]
    ]
    kernel.finish("run-1", text="one done")
    await first
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="two done")

    result = await second
    assert result.run_id == "run-2"
    assert [call["run_id"] for call in kernel.submit_calls if not call["steer"]] == [
        "run-1",
        "run-2",
    ]


@pytest.mark.asyncio
async def test_steer_race_reuses_group_and_image_parts_exactly_once(
    tmp_path: Path,
) -> None:
    """Fallback reuses prepared parts instead of a second drain or download."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    images = CountingImageResolver()
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        image_resolver=images,
    )
    first_message = inbound(chat_id="room", text="first", is_group=True)
    second_message = inbound(chat_id="room", text="second", is_group=True)
    request = _request(second_message, catalog)
    buffer_key = "agent-a:web_relay:room"

    first = asyncio.create_task(coordinator.dispatch(_request(first_message, catalog)))
    await kernel.wait_stream("run-1")
    group_store.append(buffer_key, "background once", sender="Bob")
    fallback = asyncio.create_task(coordinator.dispatch(request))
    await kernel.wait_submit_count(2)
    steer_parts = kernel.submit_calls[1]["parts"]

    kernel.finish("run-1")
    await first
    await kernel.wait_stream("run-2")
    fallback_parts = kernel.submit_calls[-1]["parts"]
    kernel.finish("run-2")
    await fallback

    assert images.calls == 2  # first message + second message, not fallback again
    assert steer_parts == fallback_parts
    assert [part["text"] for part in fallback_parts] == [
        "[Bob] background once",
        "[Alice] second",
    ]
    assert group_store.drain(buffer_key) == []


@pytest.mark.asyncio
async def test_stop_observes_marker_before_first_post_submit_await(
    tmp_path: Path,
) -> None:
    """The accepted callback pause cannot expose a Kernel-admitted idle gap."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    accepted = asyncio.Event()
    release_callback = asyncio.Event()

    async def _lifecycle(_message, update) -> None:
        if update.phase == "accepted":
            accepted.set()
            await release_callback.wait()

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        relay_lifecycle_callback=_lifecycle,
    )
    message = inbound(chat_id="chat-a", text="work")
    request = _request(message, catalog)
    running = asyncio.create_task(coordinator.dispatch(request))
    await asyncio.wait_for(accepted.wait(), timeout=1)

    stopped = await coordinator.stop(
        StopRunRequest(
            message=inbound(chat_id="chat-a", text="/stop"),
            agent=request.agent,
            session_key=request.session_key,
        )
    )

    assert stopped.run_id == "run-1"
    assert kernel.operations[:3] == [
        ("submit", "run-1"),
        ("interrupt", "run-1"),
        ("append", "run-1"),
    ]
    release_callback.set()
    kernel.finish("run-1", status="cancelled", text="")
    await running


@pytest.mark.asyncio
async def test_bounded_lock_registry_cannot_evict_pre_submit_session_owner(
    tmp_path: Path,
) -> None:
    """Capacity pressure cannot let stop bypass another session's pre-submit lock."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    images = _GatedImageResolver(2)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        image_resolver=images,
        max_transition_locks=1,
    )
    message_a = inbound(chat_id="chat-a", text="first")
    message_b = inbound(chat_id="chat-b", text="second")

    running_a = asyncio.create_task(coordinator.dispatch(_request(message_a, catalog)))
    await asyncio.wait_for(images.entered[0].wait(), timeout=1)
    running_b = asyncio.create_task(coordinator.dispatch(_request(message_b, catalog)))
    await asyncio.wait_for(images.entered[1].wait(), timeout=1)

    stopping_b = asyncio.create_task(
        coordinator.stop(
            StopRunRequest(
                message=inbound(chat_id="chat-b", text="/stop"),
                agent=catalog.require("agent-a"),
                session_key=build_session_key(message_b, agent_id="agent-a"),
            )
        )
    )
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(asyncio.shield(stopping_b), timeout=0.05)

    images.release[1].set()
    await kernel.wait_stream("run-1")
    stopped = await asyncio.wait_for(stopping_b, timeout=1)
    assert stopped.run_id == "run-1"
    assert stopped.reply_text == "已停止当前操作。"
    kernel.finish("run-1", status="cancelled", text="")
    await running_b

    images.release[0].set()
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="first done")
    assert (await running_a).reply_text == "first done"


@pytest.mark.asyncio
async def test_continuous_steer_uses_one_original_stream(
    tmp_path: Path,
) -> None:
    """Multiple admitted interjections inject without opening extra consumers."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    running = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="one"), catalog))
    )
    await kernel.wait_stream("run-1")
    kernel.inject_steer = True

    two = await coordinator.dispatch(
        _request(inbound(chat_id="chat-a", text="two"), catalog)
    )
    three = await coordinator.dispatch(
        _request(inbound(chat_id="chat-a", text="three"), catalog)
    )

    assert two.run_id == three.run_id == "run-1"
    assert [call["steer"] for call in kernel.submit_calls] == [False, True, True]
    kernel.finish("run-1", text="all done")
    assert (await running).reply_text == "all done"


@pytest.mark.asyncio
async def test_active_run_keeps_original_session_across_config_publish(
    tmp_path: Path,
) -> None:
    """Steer and stop control the admitted session until its terminal event."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    old_request = _request(inbound(chat_id="chat-a", text="old run"), catalog)
    running = asyncio.create_task(coordinator.dispatch(old_request))
    await kernel.wait_stream("run-1")

    new_workspace = tmp_path / "agent-a-v2"
    new_workspace.mkdir()
    current = catalog.publish(
        AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=new_workspace,
            title="Agent A v2",
        )
    )
    binder.invalidate_stale("agent-a", current_revision=current.revision)
    kernel.inject_steer = True

    steered = await coordinator.dispatch(
        _request(inbound(chat_id="chat-a", text="new follow-up"), catalog)
    )
    stopped = await coordinator.stop(
        StopRunRequest(
            message=inbound(chat_id="chat-a", text="/stop"),
            agent=current,
            session_key=old_request.session_key,
        )
    )

    assert steered.run_id == stopped.run_id == "run-1"
    assert kernel.submit_calls[-1]["session_id"] == "sess-1"
    assert kernel.interrupt_calls == ["sess-1"]
    assert kernel.append_calls[-1]["session_id"] == "sess-1"
    assert kernel.create_calls == [str(old_request.agent.config.workspace_root)]

    kernel.finish("run-1", status="cancelled", text="")
    await running
    next_run = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="v2"), catalog))
    )
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="v2 done")
    assert (await next_run).kernel_session_id == "sess-2"
    assert kernel.create_calls[-1] == str(new_workspace)
