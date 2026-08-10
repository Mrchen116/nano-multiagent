"""Public admission and linearization behavior of SessionRunCoordinator."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    InboundIngress,
)

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.inbound_models import (
    CompactSessionRequest,
    GatewayShadowState,
    InboundRunRequest,
    NewSessionRequest,
    RoutedInbound,
    ShadowConversationRef,
    StopRunRequest,
)
from personal_assistant.gateway.image_attachments import ImageResolution
from personal_assistant.gateway.session_keys import (
    PersistentSessionBindingStore,
    SessionBindingStore,
    build_session_key,
)
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator
from personal_assistant.gateway.readable_input_projection import (
    ReadableInputProjectionStore,
)

from ._session_run_coordinator_helpers import (
    CountingImageResolver,
    build_dependencies,
    inbound,
)


def _request(
    message,
    catalog,
    *,
    shadow: GatewayShadowState = GatewayShadowState(),
) -> InboundRunRequest:
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        routed=RoutedInbound(message=message, shadow=shadow),
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


def _new_request(
    message,
    catalog,
    *,
    operation_id: str | None = None,
    shadow: GatewayShadowState = GatewayShadowState(),
) -> NewSessionRequest:
    agent = catalog.require("agent-a")
    return NewSessionRequest(
        routed=RoutedInbound(message=message, shadow=shadow),
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        operation_id=operation_id,
    )


def _compact_request(
    message,
    catalog,
    *,
    operation_id: str | None = None,
    shadow: GatewayShadowState = GatewayShadowState(),
) -> CompactSessionRequest:
    agent = catalog.require("agent-a")
    return CompactSessionRequest(
        routed=RoutedInbound(message=message, shadow=shadow),
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        operation_id=operation_id,
    )


@pytest.mark.asyncio
async def test_new_suppresses_a_running_old_final_before_confirming_fresh_session(
    tmp_path: Path,
) -> None:
    store = SessionBindingStore()
    kernel, catalog, binder, router, group_store = build_dependencies(
        tmp_path, session_store=store
    )
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    message = inbound(chat_id="chat-a", text="old work")
    running = asyncio.create_task(coordinator.dispatch(_request(message, catalog)))
    await kernel.wait_stream("run-1")

    reset = await coordinator.new_session(
        _new_request(
            inbound(chat_id="chat-a", text="/new"),
            catalog,
            operation_id="relay:new-1",
        )
    )
    kernel.finish("run-1", text="late old output")
    old = await running

    assert reset.reply_text == "已停止当前操作，并已开始新会话。"
    assert reset.kernel_session_id == "sess-2"
    assert kernel.interrupt_calls == ["sess-1"]
    assert old.outbound is None
    assert old.reply_text == "late old output"
    assert store.get("web_relay:chat-a:agent-a").kernel_session_id == "sess-2"


@pytest.mark.asyncio
async def test_new_drops_a_queued_old_request_instead_of_submitting_it_to_new_context(
    tmp_path: Path,
) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    first = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="first"), catalog))
    )
    await kernel.wait_stream("run-1")
    queued = asyncio.create_task(
        coordinator.dispatch(
            _request(inbound(chat_id="chat-a", text="queued"), catalog)
        )
    )
    await kernel.wait_try_steer_count(1)

    await coordinator.new_session(
        _new_request(inbound(chat_id="chat-a", text="/new"), catalog)
    )
    kernel.finish("run-1", text="old")

    queued_result = await queued
    await first
    assert [
        call["parts"][0]["text"] for call in kernel.submit_calls if not call["steer"]
    ] == ["first"]
    assert queued_result.outbound is None
    assert queued_result.run_id == ""


@pytest.mark.asyncio
async def test_compact_queues_behind_active_work_and_becomes_a_fifo_barrier(
    tmp_path: Path,
) -> None:
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

    compact = asyncio.create_task(
        coordinator.compact(
            _compact_request(
                inbound(chat_id="chat-a", text="/compact"),
                catalog,
                operation_id="relay:compact-1",
            )
        )
    )
    await asyncio.sleep(0)
    assert not compact.done()
    assert kernel.compact_calls == []

    later = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="later"), catalog))
    )
    await asyncio.sleep(0)
    assert kernel.try_steer_calls == []

    kernel.finish("run-1")
    await first
    compact_result = await compact
    assert compact_result.reply_text == "已压缩当前会话。"
    assert kernel.compact_calls == [
        {
            "session_id": "sess-1",
            "workspace_root": str(catalog.require("agent-a").config.workspace_root),
            "focus": None,
            "idempotency_key": "relay:compact-1",
        }
    ]

    await kernel.wait_stream("run-2")
    kernel.finish("run-2")
    await later


@pytest.mark.asyncio
async def test_new_supersedes_a_queued_compact_and_persists_its_replay_outcome(
    tmp_path: Path,
) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    first = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="first"), catalog))
    )
    await kernel.wait_stream("run-1")
    compact_request = _compact_request(
        inbound(chat_id="chat-a", text="/compact"),
        catalog,
        operation_id="relay:compact-before-new",
    )
    compact = asyncio.create_task(coordinator.compact(compact_request))
    await asyncio.sleep(0)

    await coordinator.new_session(
        _new_request(
            inbound(chat_id="chat-a", text="/new"),
            catalog,
            operation_id="relay:new-after-compact",
        )
    )
    kernel.finish("run-1")
    await first
    compact_result = await compact

    assert compact_result.reply_text == "已开始新会话，未执行之前的压缩请求。"
    assert kernel.compact_calls == []
    outcome = binder.completed_control(
        session_key=compact_request.session_key,
        operation_id="relay:compact-before-new",
        kind="compact",
    )
    assert outcome is not None
    assert outcome.status == "superseded"

    replay = await coordinator.compact(compact_request)

    assert replay.reply_text == "已开始新会话，未执行之前的压缩请求。"
    assert kernel.compact_calls == []


@pytest.mark.asyncio
async def test_failed_new_restores_old_delivery_and_confirms_current_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    delivery_events: list[str] = []

    async def quiesce(run_id: str) -> None:
        delivery_events.append(f"quiesce:{run_id}")

    def restore(run_id: str) -> None:
        delivery_events.append(f"restore:{run_id}")

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        quiesce_run_delivery=quiesce,
        restore_run_delivery=restore,
    )
    running = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="old"), catalog))
    )
    await kernel.wait_stream("run-1")

    def fail_publish(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("simulated binding failure")

    monkeypatch.setattr(binder, "publish_reset", fail_publish)
    result = await coordinator.new_session(
        _new_request(
            inbound(chat_id="chat-a", text="/new"),
            catalog,
            operation_id="relay:new-failure",
        )
    )

    assert result.reply_text == "未能开始新会话，当前会话保持不变。"
    outcome = binder.completed_control(
        session_key="web_relay:chat-a:agent-a",
        operation_id="relay:new-failure",
        kind="new",
    )
    assert outcome is not None
    assert outcome.status == "failed"
    assert delivery_events == ["quiesce:run-1", "restore:run-1"]
    assert kernel.interrupt_calls == []
    kernel.finish("run-1", text="old output still visible")
    assert (await running).reply_text == "old output still visible"


@pytest.mark.asyncio
async def test_failed_external_new_persists_recoverable_confirmation_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed Feishu reset is replay-safe even before it has an IM binding."""
    store = PersistentSessionBindingStore(db_path=tmp_path / "bindings.sqlite3")
    kernel, catalog, binder, router, group_store = build_dependencies(
        tmp_path, session_store=store
    )
    delivery_drains: list[str] = []

    async def drain() -> None:
        delivery_drains.append("drain")

    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        drain_external_control_deliveries=drain,
    )

    async def fail_prepare(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("fresh session unavailable")

    monkeypatch.setattr(binder, "prepare_reset", fail_prepare)
    external_message = replace(
        inbound(chat_id="oc-external", text="/new"),
        ingress=InboundIngress(
            external_conversation=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="oc-external",
                agent_id="agent-a",
                trigger_source="feishu",
            ),
        ),
    )

    result = await coordinator.new_session(
        _new_request(
            external_message,
            catalog,
            operation_id="feishu:new-failure",
            shadow=GatewayShadowState(saga_id="saga-failed-new"),
        )
    )

    assert result.reply_text == "未能开始新会话，当前会话保持不变。"
    assert delivery_drains == ["drain"]
    pending = store.pending_external_controls()
    assert len(pending) == 1
    assert pending[0].outcome.status == "failed"
    assert pending[0].shadow_saga_id == "saga-failed-new"


@pytest.mark.asyncio
async def test_runtime_replacement_persists_web_anchor_before_submit(
    tmp_path: Path,
) -> None:
    """A changed retained runtime records a durable divider anchored to this message."""

    store = SessionBindingStore()
    kernel, catalog, binder, router, group_store = build_dependencies(
        tmp_path, session_store=store
    )
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        node_id="node-1",
    )
    first_message = inbound(chat_id="conversation-1", text="before")
    first = asyncio.create_task(
        coordinator.dispatch(
            _request(
                first_message,
                catalog,
                shadow=GatewayShadowState(
                    saga_id="saga-before",
                    ref=ShadowConversationRef(
                        conversation_id="conversation-1",
                        im_message_id="message-before",
                    ),
                ),
            )
        )
    )
    await kernel.wait_stream("run-1")
    kernel.finish("run-1")
    await first

    current = catalog.require("agent-a").config
    catalog.publish(replace(current, default_model="updated-model"))
    changed_message = inbound(chat_id="conversation-1", text="after")
    changed = asyncio.create_task(
        coordinator.dispatch(
            _request(
                changed_message,
                catalog,
                shadow=GatewayShadowState(
                    saga_id="saga-after",
                    ref=ShadowConversationRef(
                        conversation_id="conversation-1",
                        im_message_id="message-after",
                    ),
                ),
            )
        )
    )
    await kernel.wait_stream("run-2")

    assert store.pending_boundaries()[0].before_message_id == "message-after"
    assert kernel.reconfigure_calls[-1][1].model == "updated-model"

    kernel.finish("run-2")
    await changed


@pytest.mark.asyncio
async def test_external_runtime_replacement_waits_for_saga_anchor_before_boundary_delivery(
    tmp_path: Path,
) -> None:
    """An offline shadow event promotes one divider only after its user anchor exists."""

    store = PersistentSessionBindingStore(db_path=tmp_path / "session_bindings.sqlite3")
    kernel, catalog, binder, router, group_store = build_dependencies(
        tmp_path, session_store=store
    )
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        node_id="node-1",
    )
    first = asyncio.create_task(
        coordinator.dispatch(
            _request(inbound(chat_id="external-chat", text="before"), catalog)
        )
    )
    await kernel.wait_stream("run-1")
    kernel.finish("run-1")
    await first

    current = catalog.require("agent-a").config
    catalog.publish(replace(current, default_model="updated-model"))
    pending_message = inbound(chat_id="external-chat", text="after")
    changed = asyncio.create_task(
        coordinator.dispatch(
            _request(
                pending_message,
                catalog,
                shadow=GatewayShadowState(saga_id="saga-1"),
            )
        )
    )
    await kernel.wait_stream("run-2")

    assert store.pending_boundaries() == ()

    promoted = store.promote_pending_boundary(
        shadow_saga_id="saga-1",
        shadow_ref=ShadowConversationRef(
            conversation_id="shadow-conversation", im_message_id="shadow-user-message"
        ),
    )

    assert promoted is not None
    assert promoted.conversation_id == "shadow-conversation"
    assert promoted.before_message_id == "shadow-user-message"
    assert store.pending_boundaries() == (promoted,)
    assert (
        store.promote_pending_boundary(
            shadow_saga_id="saga-1",
            shadow_ref=ShadowConversationRef(
                conversation_id="shadow-conversation",
                im_message_id="shadow-user-message",
            ),
        )
        is None
    )
    assert store.pending_boundaries() == (promoted,)

    kernel.finish("run-2")
    await changed


@pytest.mark.asyncio
async def test_unknown_legacy_runtime_establishes_baseline_without_boundary(
    tmp_path: Path,
) -> None:
    """An unreadable legacy runtime adopts desired config without a false divider."""

    store = SessionBindingStore()
    kernel, catalog, binder, router, group_store = build_dependencies(
        tmp_path, session_store=store
    )
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        node_id="node-1",
    )
    first_message = inbound(chat_id="conversation-1", text="before")
    first = asyncio.create_task(
        coordinator.dispatch(
            _request(
                first_message,
                catalog,
                shadow=GatewayShadowState(
                    saga_id="saga-before",
                    ref=ShadowConversationRef(
                        conversation_id="conversation-1",
                        im_message_id="message-before",
                    ),
                ),
            )
        )
    )
    await kernel.wait_stream("run-1")
    kernel.finish("run-1")
    await first

    kernel.return_no_runtime = True
    store.apply_runtime(
        store.get("web_relay:conversation-1:agent-a"),
        runtime_fingerprint="legacy-runtime",
        fingerprint_schema="legacy-v0",
        profile_version=None,
    )
    changed_message = inbound(chat_id="conversation-1", text="after")

    changed = asyncio.create_task(
        coordinator.dispatch(
            _request(
                changed_message,
                catalog,
                shadow=GatewayShadowState(
                    saga_id="saga-after",
                    ref=ShadowConversationRef(
                        conversation_id="conversation-1",
                        im_message_id="message-after",
                    ),
                ),
            )
        )
    )
    await kernel.wait_stream("run-2")

    assert store.pending_boundaries() == ()

    kernel.finish("run-2")
    await changed


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
async def test_active_steer_reuses_decorated_parts_without_staging_readable_history(
    tmp_path: Path,
) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    readable_store = ReadableInputProjectionStore()
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        readable_input_projection_store=readable_store,
    )
    first = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="one"), catalog))
    )
    await kernel.wait_stream("run-1")
    kernel.inject_steer = True
    header = "[Web IM Mon 2026-08-10 09:17 CST]"
    second_message = replace(
        inbound(chat_id="chat-a", text="two"),
        metadata={
            "_pa_human_message_context": {
                "version": 1,
                "header": header,
                "time_zone": "Asia/Shanghai",
            }
        },
    )

    injected = await coordinator.dispatch(_request(second_message, catalog))

    assert injected.run_id == "run-1"
    assert kernel.try_steer_calls[-1]["parts"] == [
        {"type": "text", "text": f"{header} two"}
    ]
    assert readable_store.resolve_exact("sess-1", f"{header} two") is None
    kernel.finish("run-1")
    await first


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
            routed=RoutedInbound(message=inbound(chat_id="chat-a", text="/stop")),
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
                routed=RoutedInbound(message=inbound(chat_id="chat-b", text="/stop")),
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
async def test_batched_consumed_steer_uses_the_last_follower_shadow_anchor(
    tmp_path: Path,
) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    observed: list[dict[str, object]] = []
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        kernel_event_observer=lambda event: observed.append(dict(event)),
    )
    primary_message = inbound(chat_id="chat-a", text="one")
    running = asyncio.create_task(
        coordinator.dispatch(
            _request(
                primary_message,
                catalog,
                shadow=GatewayShadowState(saga_id="saga-1"),
            )
        )
    )
    await kernel.wait_stream("run-1")
    kernel.inject_steer = True
    follower_message = inbound(chat_id="chat-a", text="two")
    last_follower_message = inbound(chat_id="chat-a", text="three")

    steered = await coordinator.dispatch(
        _request(
            follower_message,
            catalog,
            shadow=GatewayShadowState(saga_id="saga-2"),
        )
    )
    assert steered.run_id == "run-1"
    last_steered = await coordinator.dispatch(
        _request(
            last_follower_message,
            catalog,
            shadow=GatewayShadowState(
                saga_id="saga-3",
                ref=ShadowConversationRef(
                    conversation_id="shadow-3",
                    im_message_id="message-3",
                ),
            ),
        )
    )
    assert last_steered.run_id == "run-1"
    kernel.push(
        "run-1",
        {
            "event": "injection_consumed",
            "message_count": 2,
            "user_message_count": 2,
        },
    )
    kernel.finish("run-1", text="all done")
    await running

    consumed = next(
        event for event in observed if event["event"] == "injection_consumed"
    )
    assert consumed["shadow_saga_id"] == "saga-3"
    assert consumed["shadow_anchor_pending"] is False
    assert consumed["shadow_conversation_id"] == "shadow-3"


@pytest.mark.asyncio
async def test_consumed_steer_marks_a_pending_follower_shadow_anchor(
    tmp_path: Path,
) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    observed: list[dict[str, object]] = []
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        kernel_event_observer=lambda event: observed.append(dict(event)),
    )
    running = asyncio.create_task(
        coordinator.dispatch(
            _request(
                inbound(chat_id="chat-a", text="one"),
                catalog,
                shadow=GatewayShadowState(saga_id="saga-1"),
            )
        )
    )
    await kernel.wait_stream("run-1")
    kernel.inject_steer = True
    steered = await coordinator.dispatch(
        _request(
            inbound(chat_id="chat-a", text="two"),
            catalog,
            shadow=GatewayShadowState(saga_id="saga-2"),
        )
    )
    assert steered.run_id == "run-1"
    kernel.push(
        "run-1",
        {
            "event": "injection_consumed",
            "message_count": 1,
            "user_message_count": 0,
        },
    )
    kernel.push(
        "run-1",
        {
            "event": "injection_consumed",
            "message_count": 1,
            "user_message_count": 1,
        },
    )
    kernel.finish("run-1", text="all done")
    await running

    consumed_events = [
        event for event in observed if event["event"] == "injection_consumed"
    ]
    assert len(consumed_events) == 1
    consumed = consumed_events[0]
    assert consumed["shadow_saga_id"] == "saga-2"
    assert consumed["shadow_anchor_pending"] is True
    assert "shadow_conversation_id" not in consumed


@pytest.mark.asyncio
async def test_config_publish_reconfigures_same_session_only_for_next_run(
    tmp_path: Path,
) -> None:
    """A completed run keeps its transcript session while the next run adopts config."""

    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        product_default_model="fallback-model",
    )
    first_request = _request(inbound(chat_id="chat-a", text="old run"), catalog)
    first = asyncio.create_task(coordinator.dispatch(first_request))
    await kernel.wait_stream("run-1")
    kernel.finish("run-1", text="old done")
    assert (await first).kernel_session_id == "sess-1"
    assert kernel.create_runtimes[0] is not None
    assert kernel.create_runtimes[0].features == {
        "include_session_created_datetime": False
    }

    current = catalog.publish(
        AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=first_request.agent.config.workspace_root,
            title="Agent A v2",
            default_model="model-v2",
            skills=("research",),
            tool_allowlist=("read",),
            features={"memory_curation": False},
            custom_prompt="Use the replacement configuration.",
        )
    )
    next_run = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="v2"), catalog))
    )
    await kernel.wait_stream("run-2")

    assert kernel.create_calls == [str(first_request.agent.config.workspace_root)]
    assert [session_id for session_id, _ in kernel.reconfigure_calls] == ["sess-1"]
    replacement = kernel.reconfigure_calls[0][1]
    assert replacement.model == "model-v2"
    assert replacement.skills == ["research"]
    assert replacement.enabled_tools == ["read"]
    assert replacement.features == {
        "memory_curation": False,
        "include_session_created_datetime": False,
    }

    kernel.finish("run-2", text="v2 done")
    assert (await next_run).kernel_session_id == "sess-1"


@pytest.mark.asyncio
async def test_active_run_steer_keeps_original_runtime_after_config_publish(
    tmp_path: Path,
) -> None:
    """A steer belongs to its active run and never admits a newer configuration."""

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

    catalog.publish(
        AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=old_request.agent.config.workspace_root,
            title="Agent A v2",
            default_model="model-v2",
        )
    )
    kernel.inject_steer = True

    steered = await coordinator.dispatch(
        _request(inbound(chat_id="chat-a", text="new follow-up"), catalog)
    )

    assert steered.run_id == "run-1"
    assert kernel.reconfigure_calls == []
    assert kernel.submit_calls[-1]["session_id"] == "sess-1"

    kernel.finish("run-1", text="done")
    await running
