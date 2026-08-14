"""Translate kernel runtime events into Gateway delivery side effects."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from collections.abc import Awaitable, Callable, Coroutine, Mapping
import logging
from typing import Any

from personal_assistant.gateway.reply_visibility import (
    is_protocol_silence_token,
    should_suppress_reply,
)
from personal_assistant.gateway.shadow_saga import (
    ExternalShadowBubble,
    ExternalShadowBubbleEvent,
    ExternalShadowOutput,
)
from personal_assistant.gateway.workflow_permission_bindings import (
    WorkflowPermissionDelivery,
    WorkflowPermissionDeliveryAnchor,
    WorkflowPermissionDeliveryBindingRegistry,
)
from personal_assistant.ws.im_connection import IMConnectionManager

from .background import _invoke_external_reply_sender
from .context import RunDeliveryContext, RunDeliveryContextStore
from ..runtime_footer import ExternalFinalProjection, TerminalFooterFacts
from .task_tracker import RuntimeDeliveryTaskTracker

_log = logging.getLogger("personal_assistant.gateway.runtime_delivery.observer")
_SELF_EVOLUTION_SOURCE = "self_evolution"


def _live_context(
    run_context_store: RunDeliveryContextStore, run_id: str
) -> RunDeliveryContext | None:
    """Return the typed context while its run remains live."""

    return run_context_store.get(run_id)


def extract_ack_message_id(ack: Mapping[str, Any] | Any) -> str | None:
    """Pull the created bubble's message_id out of a turn_start ack frame.

    IM answers ``turn_start`` with either ``{"payload": {"message_id": ...}}`` or a
    flat ``{"message_id": ...}``. This single unwrap is the source of truth for that
    shape so the three bubble-opening paths (close-restart, steer roll, inline
    turn_start) don't each re-implement (and drift on) the isinstance dance
    (bugfix-426-M4 V2). Returns ``None`` when no message_id is present.
    """
    payload = ack.get("payload") if isinstance(ack, Mapping) else None
    source = payload if isinstance(payload, Mapping) else ack
    if not isinstance(source, Mapping):
        return None
    message_id = source.get("message_id")
    return str(message_id) if message_id else None


async def roll_bubble(
    manager: IMConnectionManager,
    *,
    run_id: str,
    conversation_id: str,
    agent_id: str,
    run_context_store: RunDeliveryContextStore,
    old_message_id: str | None,
    new_kernel_message_id: str | None = None,
    new_shadow_message_id: str | None = None,
    old_elapsed_ms: int | None = None,
    background_returns: list[dict[str, Any]] | None = None,
) -> str | None:
    """Finalize the current IM bubble and open a fresh one for the same run.

    Single primitive for "close bubble A (completed), open bubble B, repoint the run
    to B" — shared by the textA→textB multi-bubble path and the steer-consume bubble
    roll (bugfix-426-M4 V2). Returns the new bubble's message_id (already stored into
    ``run_context_store[run_id]``), or ``None`` if the run context vanished or IM
    returned no message_id.

    bugfix-426-M4 V3 reentrancy guard: two steers in quick succession produce two
    ``injection_consumed`` signals. A per-run ``rolling`` flag serializes them so the
    second caller does not re-close an already-closed bubble or open a duplicate B
    (which would leave a zombie running bubble). The flag is cleared in ``finally``.
    """
    ctx = _live_context(run_context_store, run_id)
    if ctx is None:
        return None
    if not ctx.begin_roll():
        # A roll is already in flight for this run; the in-flight one owns the
        # transition. Dropping this duplicate is safe — the steer's content still
        # streams into whatever bubble the in-flight roll lands on.
        return None
    # feat-445-M1: the bubble being closed was produced by the kernel message tracked in
    # ctx.kernel_message_id; stamp it onto the closing frame so IM persists the
    # per-bubble id BEFORE the new bubble's id overwrites ctx (decision 4 fork anchor).
    old_kernel_message_id = ctx.kernel_message_id or None
    try:
        if old_message_id:
            await manager.send_json_await_ack(
                "node.streaming_delta",
                {
                    "kind": "message_completed",
                    "message_id": old_message_id,
                    "final_content": None,
                    "token_usage": None,
                    "delivery_status": "completed",
                    "kernel_message_id": old_kernel_message_id,
                    "run_id": run_id,
                    "elapsed_ms": old_elapsed_ms,
                },
            )
        turn_start_payload: dict[str, Any] = {
            "kind": "turn_start",
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "shadow_message_id": new_shadow_message_id,
        }
        if background_returns:
            turn_start_payload["background_returns"] = background_returns
        ack = await manager.send_json_await_ack(
            "node.streaming_delta",
            turn_start_payload,
        )
        new_message_id = extract_ack_message_id(ack)
        live_ctx = _live_context(run_context_store, run_id)
        if new_message_id and live_ctx is not None:
            # These flags describe the bubble that was just closed, not the whole
            # run. Carrying either across a steer makes the new bubble inherit the
            # old bubble's visible/silence terminal decision.
            live_ctx.replace_bubble(
                message_id=new_message_id,
                kernel_message_id=new_kernel_message_id,
            )
            if background_returns:
                live_ctx.mark_visible_reply()
            return new_message_id
        if live_ctx is not None:
            live_ctx.clear_message_id()
        return None
    finally:
        live_ctx = _live_context(run_context_store, run_id)
        if live_ctx is not None:
            live_ctx.finish_roll()


def build_kernel_event_observer(
    *,
    im_connection_manager_factory: Callable[[], IMConnectionManager | None],
    run_context_store: RunDeliveryContextStore,
    running_tool_calls: dict[str, dict[str, dict[str, Any]]] | None = None,
    external_reply_sender: Callable[[str, Mapping[str, str]], Any] | None = None,
    external_final_projection_builder: (
        Callable[[str, str, TerminalFooterFacts], ExternalFinalProjection] | None
    ) = None,
    shadow_output_prepare: (
        Callable[[str, str, str, str | None, str], ExternalShadowOutput] | None
    ) = None,
    shadow_output_mirror: (
        Callable[[ExternalShadowOutput], Coroutine[Any, Any, None]] | None
    ) = None,
    shadow_bubble_record: (
        Callable[[ExternalShadowBubbleEvent], ExternalShadowBubble] | None
    ) = None,
    shadow_bubble_reconcile: (
        Callable[[ExternalShadowBubble], Coroutine[Any, Any, None]] | None
    ) = None,
    shadow_pending_notify: Callable[[], None] | None = None,
    external_permission_request_sender: (
        Callable[[Mapping[str, Any], Mapping[str, str]], Any] | None
    ) = None,
    external_permission_resolved_sender: (
        Callable[[str, str, Mapping[str, str]], Any] | None
    ) = None,
    skill_created_handler: Callable[[str, Mapping[str, object]], Any] | None = None,
    task_tracker: RuntimeDeliveryTaskTracker | None = None,
    workflow_permission_bindings: WorkflowPermissionDeliveryBindingRegistry
    | None = None,
    workflow_permission_delivery: Callable[
        [WorkflowPermissionDelivery], Awaitable[None]
    ]
    | None = None,
) -> Callable[[Mapping[str, Any]], "Coroutine[Any, Any, None] | None"]:
    """Build a kernel SSE event observer that forwards streaming events to IM via node.streaming_delta.

    The observer returns a coroutine for run_status=running so the pipeline can
    await the turn_start ack before processing the following assistant_message event.
    For all other events the observer schedules tasks and returns None.

    Kernel SSE events translated:
    - run_status=running  → node.streaming_delta kind=turn_start (creates placeholder message)
    - assistant_message   → node.streaming_delta kind=message_delta
    - tool_start          → node.streaming_delta kind=tool_call_upserted
    - tool_end            → node.streaming_delta kind=tool_call_completed
    - turn_end            → node.streaming_delta kind=message_completed (with token_usage if available)

    Heartbeat lazy-bubble path (feat-393):
    - run_context_store entries with ``to_user_id`` (no ``conversation_id``) are heartbeat runs.
    - turn_start is deferred until the first non-empty, non-NO_REPLY assistant_message arrives.
    - NO_REPLY/empty content → no turn_start is ever sent → zero IM trace (silent tick).
    - Normal chat eagerly creates a provisional placeholder on run_status=running.
      Suppression-enabled contexts roll that placeholder back if the complete reply
      is a protocol silence token.

    Canonical session (feat-394 decision 3):
    - HeartbeatScheduler.tick() calls session_store.find_direct_by_agent() BEFORE each run
      submission to update canonical_session_store — tick-time read, no ack dependency.
    """

    # bugfix-410-M2 R3 (#97): track tool_calls that received tool_start but not yet
    # tool_end, per run. On abnormal run termination the watchdog/terminal path emits
    # a synthetic ``run_terminal_reconcile`` event; we then close every still-running
    # tool_call with a reason so the IM badge stops spinning forever. Keyed by run_id
    # → {call_id: {"name": ..., "input": ..., "output": ..., "detail": ..., "emoji": ...}}.
    # bugfix-416 #111 retained input; bugfix-441-M2 also retains the start-side
    # presentation so abnormal reconcile does not erase the running row's parameter
    # display from refreshed/historical IM payloads.
    # bugfix-410-fix-r1: the map is injectable purely so a test can observe that the
    # per-run entry is reaped on the normal-completion path (no production caller passes
    # it). Entries are dropped as calls close (tool_end) and as runs end (turn_end /
    # reconcile), so this never grows unbounded on a long-lived Gateway.
    if running_tool_calls is None:
        running_tool_calls = {}
    if task_tracker is None:
        # Direct observer tests and library callers keep a local owner. Production
        # always injects the composition-root singleton so GatewayRuntime can drain it.
        task_tracker = RuntimeDeliveryTaskTracker()
    visible_reasoning_by_group: dict[str, dict[str, str]] = {}
    durable_reasoning_by_group: dict[str, dict[str, str]] = {}
    external_reply_lock = asyncio.Lock()

    def _dispatch_workflow_permission_deliveries(
        deliveries: tuple[WorkflowPermissionDelivery, ...],
    ) -> None:
        if workflow_permission_delivery is None:
            return
        for delivery in deliveries:
            task_tracker.start(
                workflow_permission_delivery(delivery),
                name=(
                    "workflow-permission:"
                    f"{delivery.event.get('workflow_run_id')}:"
                    f"{delivery.event.get('request_id')}"
                ),
                run_id=delivery.anchor.parent_run_id,
            )

    async def _send(
        manager: IMConnectionManager, message_type: str, payload: Mapping[str, Any]
    ) -> None:
        try:
            await manager.send_json(message_type, payload)
        except Exception as exc:  # noqa: BLE001
            # IM send failure must not propagate into the event stream; log so the
            # drop is observable (refactor-395-M1).
            _log.warning("IM observer send failed for %s: %s", message_type, exc)

    def _is_external_reply_context(ctx: RunDeliveryContext) -> bool:
        return (
            external_reply_sender is not None
            and _external_context_metadata(ctx) is not None
        )

    def _external_context_metadata(ctx: RunDeliveryContext) -> dict[str, str] | None:
        channel_name = ctx.reply_channel_name
        target_chat_id = ctx.reply_target_chat_id
        if (
            ctx.trigger_source == "im"
            or not channel_name
            or channel_name == "web_relay"
            or not target_chat_id
        ):
            return None
        metadata: dict[str, str] = {
            "channel_name": channel_name,
            "target_chat_id": target_chat_id,
        }
        if ctx.reply_thread_id:
            metadata["reply_thread_id"] = ctx.reply_thread_id
        if ctx.feishu_message_id:
            metadata["feishu_message_id"] = ctx.feishu_message_id
        return metadata

    async def _deliver_external_reply(
        *,
        sender: Callable[[str, Mapping[str, str]], Any],
        rid: str,
        phase: str,
        text: str,
        metadata: Mapping[str, str],
    ) -> None:
        """Deliver one normal external reply without holding the Gateway loop."""

        try:
            # Normal observer events were previously serialized by their synchronous
            # sender on this loop. Keep that provider-facing order while moving the
            # REST/retry work itself to the shared non-blocking delivery seam.
            async with external_reply_lock:
                await _invoke_external_reply_sender(
                    sender,
                    text,
                    metadata,
                )
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "external reply delivery failed (run=%s phase=%s channel=%s target=%s): %s",
                rid,
                phase,
                metadata.get("channel_name", ""),
                metadata.get("target_chat_id", ""),
                exc,
            )

    def _mirror_external_reply(
        *, rid: str, ctx: RunDeliveryContext, phase: str, text: str
    ) -> None:
        if not _is_external_reply_context(ctx):
            return
        sender = external_reply_sender
        if sender is None:
            return
        cleaned_text = text.strip()
        if not cleaned_text:
            return
        if is_protocol_silence_token(cleaned_text):
            return
        external_metadata = _external_context_metadata(ctx)
        if external_metadata is None:
            return
        projection = ctx.external_final_projection if phase == "final" else None
        external_text = projection.text if projection is not None else cleaned_text
        kernel_message_id = ctx.kernel_message_id or None
        saga_id = ctx.shadow_saga_id
        if (
            saga_id
            and shadow_output_prepare is not None
            and shadow_bubble_record is None
        ):
            output = shadow_output_prepare(
                saga_id,
                rid,
                phase,
                kernel_message_id,
                cleaned_text,
            )
            if shadow_output_mirror is not None:
                task_tracker.start(
                    shadow_output_mirror(output),
                    name=f"shadow-agent-mirror:{rid}:{phase}",
                    run_id=rid,
                )
        bubble_key = kernel_message_id or ctx.message_id or f"text:{cleaned_text}"
        metadata: dict[str, str] = {
            "reply_phase": phase,
            "reply_dedupe_key": f"{rid}:bubble:{bubble_key}",
            **external_metadata,
        }
        if projection is not None and projection.runtime_footer:
            metadata["runtime_footer"] = projection.runtime_footer
        task_tracker.start(
            _deliver_external_reply(
                sender=sender,
                rid=rid,
                phase=phase,
                text=external_text,
                metadata=metadata,
            ),
            name=f"external-reply:{rid}:{phase}",
            run_id=rid,
        )

    def _mirror_external_permission_request(
        *, rid: str, ctx: RunDeliveryContext, request: Mapping[str, Any]
    ) -> None:
        if external_permission_request_sender is None:
            return
        metadata = _external_context_metadata(ctx)
        if metadata is None:
            return
        metadata["run_id"] = rid
        result = external_permission_request_sender(request, metadata)
        if asyncio.iscoroutine(result):
            task_tracker.start(
                result, name=f"external-permission-request:{rid}", run_id=rid
            )

    def _mirror_external_permission_resolved(
        *, ctx: RunDeliveryContext, request_id: str, decision: str
    ) -> None:
        if external_permission_resolved_sender is None:
            return
        metadata = _external_context_metadata(ctx)
        if metadata is None:
            return
        result = external_permission_resolved_sender(request_id, decision, metadata)
        if asyncio.iscoroutine(result):
            task_tracker.start(
                result,
                name=f"external-permission-resolved:{request_id}",
            )

    def _mirror_external_current_as_intermediate(
        *, rid: str, ctx: RunDeliveryContext
    ) -> None:
        current_text = ctx.external_current_text
        if not current_text.strip():
            return
        marker = ctx.kernel_message_id or f"text:{current_text.strip()}"
        if ctx.external_intermediate_sent_marker == marker:
            return
        _mirror_external_reply(
            rid=rid,
            ctx=ctx,
            phase="intermediate",
            text=current_text,
        )
        ctx.mark_external_intermediate_sent(marker)

    def _next_visible_reasoning(*, rid: str, group_id: str, reasoning: str) -> str:
        if not reasoning or not group_id:
            return reasoning
        groups = visible_reasoning_by_group.get(rid, {})
        previous = groups.get(group_id)
        if previous == reasoning:
            return ""
        if previous and reasoning.startswith(previous):
            return reasoning[len(previous) :].strip()
        return reasoning

    def _mark_visible_reasoning(*, rid: str, group_id: str, reasoning: str) -> None:
        if reasoning and group_id:
            visible_reasoning_by_group.setdefault(rid, {})[group_id] = reasoning

    def _clear_run_visible_reasoning(rid: str) -> None:
        visible_reasoning_by_group.pop(rid, None)
        durable_reasoning_by_group.pop(rid, None)

    def _record_shadow(
        *,
        rid: str,
        ctx: RunDeliveryContext,
        kind: str,
        **facts: Any,
    ) -> ExternalShadowBubble | None:
        saga_id = ctx.shadow_saga_id
        if not saga_id or shadow_bubble_record is None:
            return None
        snapshot = shadow_bubble_record(
            ExternalShadowBubbleEvent(
                kind=kind,  # type: ignore[arg-type]
                saga_id=saga_id,
                run_id=rid,
                **facts,
            )
        )
        ctx.record_shadow_snapshot(snapshot.shadow_message_id)
        return snapshot

    def _notify_shadow_pending() -> None:
        if shadow_pending_notify is not None:
            shadow_pending_notify()

    def _finish_shadow_live_run(
        manager: IMConnectionManager | None, *, rid: str
    ) -> None:
        finish = getattr(manager, "finish_external_shadow_run", None)
        if callable(finish):
            finish(rid)

    def _clear_live_bubble_context(*, rid: str, clear_conversation: bool) -> None:
        live_ctx = _live_context(run_context_store, rid)
        if live_ctx is None:
            return
        live_ctx.clear_message_id()
        if clear_conversation:
            live_ctx.resolve_conversation("")
        live_ctx.reset_bubble_state()

    async def _reconcile_ready_snapshot(snapshot: ExternalShadowBubble) -> None:
        if shadow_bubble_reconcile is None:
            return
        try:
            await shadow_bubble_reconcile(snapshot)
        except Exception:
            _notify_shadow_pending()
            raise

    def _durable_reasoning_delta(*, rid: str, group_id: str, reasoning: str) -> str:
        if not reasoning:
            return ""
        if not group_id:
            return reasoning
        groups = durable_reasoning_by_group.setdefault(rid, {})
        previous = groups.get(group_id)
        groups[group_id] = reasoning
        if previous == reasoning:
            return ""
        if previous and reasoning.startswith(previous):
            return reasoning[len(previous) :].strip()
        return reasoning

    def _turn_token_usage(
        event: Mapping[str, Any], *, turn_completed: bool
    ) -> dict[str, object] | None:
        usage_raw = event.get("usage") if turn_completed else None
        if not isinstance(usage_raw, Mapping):
            return None
        prompt = usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens")
        completion = usage_raw.get("completion_tokens") or usage_raw.get(
            "output_tokens"
        )
        if not isinstance(prompt, int) or not isinstance(completion, int):
            return None
        payload: dict[str, object] = {
            "prompt": prompt,
            "completion": completion,
            "total": prompt + completion,
        }
        context_window = event.get("context_window")
        if isinstance(context_window, int) and context_window > 0:
            payload["context_window"] = context_window
        cache_read = usage_raw.get("cache_read_tokens")
        cache_total_input = usage_raw.get("cache_total_input_tokens")
        payload["cache_read"] = cache_read if isinstance(cache_read, int) else 0
        payload["cache_total_input"] = (
            cache_total_input if isinstance(cache_total_input, int) else 0
        )
        return payload

    def _cache_external_final_projection(
        *, ctx: RunDeliveryContext, event: Mapping[str, Any]
    ) -> None:
        """Build the single terminal external projection before either send path."""

        if _external_context_metadata(ctx) is None or event.get("completed") is False:
            return
        text = ctx.external_current_text.strip()
        if not text or is_protocol_silence_token(text):
            return
        usage = event.get("usage")
        prompt = usage.get("prompt_tokens") if isinstance(usage, Mapping) else None
        if not isinstance(prompt, int):
            prompt = usage.get("input_tokens") if isinstance(usage, Mapping) else None
        context_window = event.get("context_window")
        facts = TerminalFooterFacts(
            model=ctx.model or None,
            prompt_tokens=prompt if isinstance(prompt, int) else None,
            context_window=(
                context_window if isinstance(context_window, int) else None
            ),
        )
        ctx.terminal_footer_facts = facts
        if external_final_projection_builder is None:
            ctx.external_final_projection = ExternalFinalProjection(text=text)
            return
        ctx.external_final_projection = external_final_projection_builder(
            text, ctx.reply_channel_name, facts
        )

    @dataclass(slots=True)
    class _DeliveryEventScope:
        """Typed state shared by the stable runtime-delivery event families."""

        event: Mapping[str, Any]
        manager: IMConnectionManager | None
        run_id: str
        ctx: RunDeliveryContext
        event_name: str
        conversation_id: str
        message_id: str
        agent_id: str
        to_user_id: str
        im_connected: bool
        rolled_shadow_snapshot: ExternalShadowBubble | None
        shadow_snapshot: ExternalShadowBubble | None
        shadow_process_seq: int | None
        abnormal_inflight: dict[str, dict[str, Any]]

    @dataclass(slots=True)
    class _PreparedEvent:
        """Either a shared event scope or an ordering/offline result already handled."""

        handled: bool
        scope: _DeliveryEventScope | None = None
        result: Coroutine[Any, Any, None] | None = None

    def _prepare_event(event: Mapping[str, Any]) -> _PreparedEvent:
        """Build one typed delivery scope and run shared shadow/offline ordering gates."""

        manager = im_connection_manager_factory()
        run_id = str(event.get("run_id") or "").strip()
        if not run_id:
            return _PreparedEvent(handled=True, result=None)
        ctx = _live_context(run_context_store, run_id)
        if ctx is None:
            return _PreparedEvent(handled=True, result=None)
        event_name = str(event.get("event") or "").strip()
        if isinstance(run_context_store, RunDeliveryContextStore):
            if event_name == "run_reset_discard":

                async def _discard_reset_bubble() -> None:
                    if ctx.shadow_saga_id and shadow_bubble_record is not None:
                        _record_shadow(rid=run_id, ctx=ctx, kind="discard")
                    message_id = ctx.message_id
                    if manager is not None and manager.connected and message_id:
                        await _send(
                            manager,
                            "node.streaming_delta",
                            {
                                "kind": "message_discarded",
                                "message_id": message_id,
                                "run_id": run_id,
                                "reason": "new_session",
                            },
                        )
                    _finish_shadow_live_run(manager, rid=run_id)

                return _PreparedEvent(handled=True, result=_discard_reset_bubble())
            if run_context_store.is_quiescing(run_id):

                async def _defer_until_reset_decides() -> None:
                    if not await run_context_store.await_visibility(run_id):
                        return
                    deferred = observer(event)
                    if asyncio.iscoroutine(deferred):
                        await deferred

                return _PreparedEvent(handled=True, result=_defer_until_reset_decides())
            if run_context_store.is_suppressed(run_id):
                return _PreparedEvent(handled=True, result=None)
        if event_name in {"turn_end", "run_terminal_reconcile"}:
            _clear_run_visible_reasoning(run_id)
        conversation_id = ctx.conversation_id
        message_id = ctx.message_id
        agent_id = ctx.agent_id
        # Source-marked self-evolution skill events belong exclusively to the
        # persistent session subscriber. Never add ordinary realtime events to
        # this business-event ownership exception.
        if (
            event_name == "skill_created"
            and event.get("source") == _SELF_EVOLUTION_SOURCE
        ):
            return _PreparedEvent(handled=True, result=None)
        if event_name == "skill_created" and agent_id and skill_created_handler:
            task_tracker.start(
                asyncio.to_thread(skill_created_handler, agent_id, event),
                name=f"skill-created:{agent_id}",
                run_id=run_id,
            )
            return _PreparedEvent(handled=True, result=None)

        # feat-393: heartbeat runs carry to_user_id instead of conversation_id.
        # The lazy-bubble gate: skip eager turn_start; defer to assistant_message.
        to_user_id = ctx.owner_user_id

        im_connected = manager is not None and manager.connected
        has_external_context = _external_context_metadata(ctx) is not None or bool(
            ctx.shadow_saga_id
        )
        rolled_shadow_snapshot: ExternalShadowBubble | None = None
        shadow_snapshot: ExternalShadowBubble | None = None
        shadow_process_seq: int | None = None
        consumed_shadow_anchor_pending = False
        abnormal_inflight: dict[str, dict[str, Any]] = {}
        if event_name == "run_terminal_reconcile":
            abnormal_inflight = running_tool_calls.pop(run_id, {})
        if ctx.shadow_saga_id and shadow_bubble_record is not None:
            if event_name == "run_status" and event.get("status") == "running":
                shadow_snapshot = _record_shadow(rid=run_id, ctx=ctx, kind="begin")
            elif event_name == "assistant_message":
                content = str(event.get("content") or "").strip()
                kernel_msg_id = str(event.get("message_id") or "").strip()
                prev_kernel_msg_id = ctx.kernel_message_id
                if (
                    content
                    and kernel_msg_id
                    and prev_kernel_msg_id
                    and kernel_msg_id != prev_kernel_msg_id
                ):
                    rolled_shadow_snapshot = _record_shadow(
                        rid=run_id,
                        ctx=ctx,
                        kind="terminal",
                        token_usage=None,
                        delivery_status="completed",
                    )
                    shadow_snapshot = _record_shadow(rid=run_id, ctx=ctx, kind="begin")
                elif not ctx.shadow_message_id:
                    shadow_snapshot = _record_shadow(rid=run_id, ctx=ctx, kind="begin")
                reasoning = str(event.get("reasoning_content") or "").strip()
                durable_reasoning = _durable_reasoning_delta(
                    rid=run_id,
                    group_id=str(event.get("group_id") or "").strip(),
                    reasoning=reasoning,
                )
                if durable_reasoning:
                    shadow_snapshot = _record_shadow(
                        rid=run_id,
                        ctx=ctx,
                        kind="thinking",
                        thinking_text=durable_reasoning,
                    )
                    if shadow_snapshot and shadow_snapshot.thinking:
                        shadow_process_seq = int(shadow_snapshot.thinking[-1]["seq"])
                if content:
                    shadow_snapshot = _record_shadow(
                        rid=run_id,
                        ctx=ctx,
                        kind="text",
                        content=content,
                        kernel_message_id=kernel_msg_id or None,
                    )
            elif event_name == "tool_start":
                call_id = str(event.get("call_id") or "").strip() or run_id
                presentation = event.get("presentation")
                tool_call: dict[str, Any] = {
                    "id": call_id,
                    "name": str(event.get("name") or ""),
                    "status": "running",
                    "input": event.get("arguments")
                    if isinstance(event.get("arguments"), dict)
                    else {},
                }
                if isinstance(presentation, Mapping):
                    if presentation.get("summary"):
                        tool_call["output"] = str(presentation["summary"])
                    if presentation.get("detail") is not None:
                        tool_call["detail"] = presentation["detail"]
                    if presentation.get("emoji"):
                        tool_call["emoji"] = str(presentation["emoji"])
                shadow_snapshot = _record_shadow(
                    rid=run_id, ctx=ctx, kind="tool", tool_call=tool_call
                )
                running_call = {
                    key: tool_call[key]
                    for key in ("name", "input", "output", "detail", "emoji")
                    if key in tool_call
                }
                running_tool_calls.setdefault(run_id, {})[call_id] = running_call
                if shadow_snapshot:
                    persisted = next(
                        item
                        for item in shadow_snapshot.tool_calls
                        if item.get("id") == call_id
                    )
                    shadow_process_seq = int(persisted["seq"])
            elif event_name == "tool_end":
                call_id = str(event.get("call_id") or "").strip() or run_id
                presentation = event.get("presentation")
                tool_call = {
                    "id": call_id,
                    "name": str(event.get("name") or ""),
                    "status": "failed" if event.get("error") else "completed",
                    "input": event.get("arguments")
                    if isinstance(event.get("arguments"), dict)
                    else {},
                }
                duration_ms = event.get("duration_ms")
                if isinstance(duration_ms, (int, float)):
                    tool_call["duration_ms"] = int(duration_ms)
                reason = event.get("reason_code")
                if isinstance(reason, str) and reason:
                    tool_call["reason"] = reason
                approval = event.get("approval")
                if isinstance(approval, str) and approval:
                    tool_call["approval"] = approval
                if isinstance(presentation, Mapping):
                    if presentation.get("summary"):
                        tool_call["output"] = str(presentation["summary"])
                    if presentation.get("detail") is not None:
                        tool_call["detail"] = presentation["detail"]
                    if presentation.get("emoji"):
                        tool_call["emoji"] = str(presentation["emoji"])
                shadow_snapshot = _record_shadow(
                    rid=run_id, ctx=ctx, kind="tool", tool_call=tool_call
                )
                inner = running_tool_calls.get(run_id)
                if inner is not None:
                    inner.pop(call_id, None)
                    if not inner:
                        running_tool_calls.pop(run_id, None)
                if shadow_snapshot:
                    persisted = next(
                        item
                        for item in shadow_snapshot.tool_calls
                        if item.get("id") == call_id
                    )
                    shadow_process_seq = int(persisted["seq"])
            elif event_name == "turn_end":
                turn_completed = event.get("completed") is not False
                discard = bool(ctx.discard_current_bubble) or (
                    turn_completed
                    and bool(ctx.discard_empty_completion)
                    and not bool(ctx.visible_reply_committed)
                )
                shadow_snapshot = _record_shadow(
                    rid=run_id,
                    ctx=ctx,
                    kind="discard" if discard else "terminal",
                    token_usage=_turn_token_usage(event, turn_completed=turn_completed),
                    delivery_status=(
                        None if discard else "completed" if turn_completed else "failed"
                    ),
                )
            elif event_name == "injection_consumed":
                rolled_shadow_snapshot = _record_shadow(
                    rid=run_id,
                    ctx=ctx,
                    kind="terminal",
                    token_usage=None,
                    delivery_status="completed",
                )
                consumed_shadow_saga_id = event.get("shadow_saga_id")
                if (
                    isinstance(consumed_shadow_saga_id, str)
                    and consumed_shadow_saga_id
                    and consumed_shadow_saga_id != ctx.shadow_saga_id
                ):
                    ctx.switch_shadow_saga(consumed_shadow_saga_id)
                consumed_shadow_conversation_id = event.get("shadow_conversation_id")
                if (
                    isinstance(consumed_shadow_conversation_id, str)
                    and consumed_shadow_conversation_id
                ):
                    conversation_id = consumed_shadow_conversation_id
                    ctx.resolve_conversation(consumed_shadow_conversation_id)
                consumed_shadow_anchor_pending = (
                    event.get("shadow_anchor_pending") is True
                )
                shadow_snapshot = _record_shadow(rid=run_id, ctx=ctx, kind="begin")
            elif event_name == "run_terminal_reconcile":
                reason = str(event.get("reason") or "interrupted").strip()
                terminal_output = event.get("content")
                for call_id, running_call in abnormal_inflight.items():
                    call = (
                        dict(running_call) if isinstance(running_call, Mapping) else {}
                    )
                    call.update(
                        {
                            "id": call_id,
                            "name": str(call.get("name") or running_call),
                            "status": "failed",
                            "reason": reason,
                            "input": call.get("input")
                            if isinstance(call.get("input"), dict)
                            else {},
                        }
                    )
                    if isinstance(terminal_output, str) and terminal_output:
                        call["output"] = terminal_output
                    _record_shadow(rid=run_id, ctx=ctx, kind="tool", tool_call=call)
                terminal_status = event.get("delivery_status")
                if terminal_status not in {"completed", "failed"}:
                    terminal_status = (
                        "completed" if event.get("finalize_bubble") else "failed"
                    )
                shadow_snapshot = _record_shadow(
                    rid=run_id,
                    ctx=ctx,
                    kind="terminal",
                    token_usage=None,
                    delivery_status=terminal_status,
                )
        if (
            event_name in {"turn_end", "run_terminal_reconcile"}
            and shadow_snapshot is not None
            and shadow_snapshot.state == "ready"
            and not ctx.conversation_id
        ):
            # A follower user anchor can still be recovering while this bubble
            # terminalizes. Bump the recovery generation again so a recovery pass
            # that captured its snapshot list before this moment cannot strand it.
            _notify_shadow_pending()
        if event_name == "turn_end":
            _cache_external_final_projection(ctx=ctx, event=event)
        if event_name == "injection_consumed" and consumed_shadow_anchor_pending:
            old_kernel_message_id = ctx.kernel_message_id
            _clear_live_bubble_context(rid=run_id, clear_conversation=True)
            _notify_shadow_pending()
            if not im_connected or manager is None:
                return _PreparedEvent(handled=True, result=None)

            async def _close_before_pending_shadow_anchor(
                mgr: IMConnectionManager = manager,
                old_msg_id: str = message_id,
                old_kernel_id: str | None = old_kernel_message_id,
                snapshot: ExternalShadowBubble | None = rolled_shadow_snapshot,
            ) -> None:
                if old_msg_id:
                    try:
                        await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            {
                                "kind": "message_completed",
                                "message_id": old_msg_id,
                                "final_content": None,
                                "token_usage": None,
                                "delivery_status": "completed",
                                "kernel_message_id": old_kernel_id,
                                "run_id": run_id,
                                "elapsed_ms": (
                                    snapshot.elapsed_ms
                                    if snapshot is not None
                                    else None
                                ),
                            },
                        )
                    except Exception as exc:  # noqa: BLE001
                        _notify_shadow_pending()
                        _log.warning("IM observer pending-anchor close failed: %s", exc)
                if snapshot is not None and shadow_bubble_reconcile is not None:
                    try:
                        await _reconcile_ready_snapshot(snapshot)
                    except Exception as exc:  # noqa: BLE001
                        _log.warning(
                            "IM observer pending-anchor reconcile failed: %s", exc
                        )

            return _PreparedEvent(
                handled=True, result=_close_before_pending_shadow_anchor()
            )

        if not im_connected and not has_external_context:
            return _PreparedEvent(handled=True, result=None)
        if not im_connected:
            if event_name == "assistant_message":
                content = str(event.get("content") or "").strip()
                if not content:
                    return _PreparedEvent(handled=True, result=None)
                kernel_msg_id = str(event.get("message_id") or "").strip()
                prev_kernel_msg_id = ctx.kernel_message_id
                if (
                    kernel_msg_id
                    and prev_kernel_msg_id
                    and kernel_msg_id != prev_kernel_msg_id
                ):
                    _mirror_external_current_as_intermediate(rid=run_id, ctx=ctx)
                ctx.record_assistant_text(content, kernel_message_id=kernel_msg_id)
                return _PreparedEvent(handled=True, result=None)
            if event_name in {"tool_start", "permission_request"}:
                _mirror_external_current_as_intermediate(rid=run_id, ctx=ctx)
                if event_name == "tool_start":
                    return _PreparedEvent(handled=True, result=None)
            elif event_name == "turn_end":
                running_tool_calls.pop(run_id, None)
                _finish_shadow_live_run(manager, rid=run_id)
                return _PreparedEvent(handled=True, result=None)
            elif event_name != "permission_resolved":
                if event_name == "run_terminal_reconcile":
                    _finish_shadow_live_run(manager, rid=run_id)
                return _PreparedEvent(handled=True, result=None)
        return _PreparedEvent(
            handled=False,
            scope=_DeliveryEventScope(
                event=event,
                manager=manager,
                run_id=run_id,
                ctx=ctx,
                event_name=event_name,
                conversation_id=conversation_id,
                message_id=message_id,
                agent_id=agent_id,
                to_user_id=to_user_id,
                im_connected=im_connected,
                rolled_shadow_snapshot=rolled_shadow_snapshot,
                shadow_snapshot=shadow_snapshot,
                shadow_process_seq=shadow_process_seq,
                abnormal_inflight=abnormal_inflight,
            ),
        )

    def _handle_bubble_event(
        scope: _DeliveryEventScope,
    ) -> Coroutine[Any, Any, None] | None:
        """Handle turn start, assistant deltas, and normal bubble completion."""

        event = scope.event
        manager = scope.manager
        run_id = scope.run_id
        ctx = scope.ctx
        event_name = scope.event_name
        conversation_id = scope.conversation_id
        message_id = scope.message_id
        agent_id = scope.agent_id
        to_user_id = scope.to_user_id
        im_connected = scope.im_connected
        rolled_shadow_snapshot = scope.rolled_shadow_snapshot
        shadow_snapshot = scope.shadow_snapshot
        shadow_process_seq = scope.shadow_process_seq

        if event_name == "run_status" and event.get("status") == "running":
            raw_background_returns = event.get("background_returns")
            background_returns = (
                [
                    dict(item)
                    for item in raw_background_returns
                    if isinstance(item, Mapping)
                ]
                if isinstance(raw_background_returns, list)
                else []
            )
            if to_user_id:
                # Heartbeat: skip eager turn_start; bubble is created lazily on first
                # real content (see assistant_message branch below).
                return None
            if conversation_id and agent_id:
                # Return a coroutine so the pipeline awaits turn_start ack before processing
                # the following assistant_message; without awaiting, message_id would still be
                # empty when assistant_message fires and the delta would be silently dropped.
                async def _send_turn_start_and_store(
                    mgr: IMConnectionManager = manager,
                    rid: str = run_id,
                    cid: str = conversation_id,
                    aid: str = agent_id,
                ) -> None:
                    try:
                        turn_start_payload: dict[str, Any] = {
                            "kind": "turn_start",
                            "conversation_id": cid,
                            "agent_id": aid,
                            "run_id": rid,
                            "shadow_message_id": ctx.shadow_message_id,
                        }
                        if background_returns:
                            turn_start_payload["background_returns"] = (
                                background_returns
                            )
                        ack = await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            turn_start_payload,
                        )
                        ack_payload = (
                            ack.get("payload")
                            if isinstance(ack.get("payload"), dict)
                            else ack
                        )
                        returned_msg_id = (
                            ack_payload.get("message_id")
                            if isinstance(ack_payload, dict)
                            else None
                        )
                        live_ctx = _live_context(run_context_store, rid)
                        if returned_msg_id and live_ctx is not None:
                            live_ctx.backfill_turn_start_ack(
                                message_id=str(returned_msg_id)
                            )
                            if background_returns:
                                live_ctx.mark_visible_reply()
                    except Exception as exc:  # noqa: BLE001
                        _log.warning("IM observer turn_start send/ack failed: %s", exc)

                return _send_turn_start_and_store()

        elif event_name == "assistant_message":
            content = str(event.get("content") or "").strip()
            kernel_msg_id = str(event.get("message_id") or "").strip()
            source_event_id = (
                event.get("_id") or event.get("sequence_num") or kernel_msg_id
            )
            delta_idempotency_key = (
                f"{run_id}:assistant_message:{source_event_id}"
                if source_event_id
                else None
            )
            prev_kernel_msg_id = ctx.kernel_message_id
            visibility_policy = ctx.visibility_policy
            if should_suppress_reply(content, policy=visibility_policy):
                # The eager normal-chat placeholder is provisional until assistant
                # content commits it. A first-bubble silence token rolls that row back;
                # a later token merely declines to open another bubble, preserving the
                # preceding real assistant message.
                ctx.mark_suppressed_reply()
                return None
            # A later real assistant message supersedes an earlier provisional silence
            # decision in the same run and commits the existing bubble normally.
            ctx.preserve_current_bubble()
            if content:
                # Tool/thinking frames are process metadata, not a user-visible reply.
                # The direct-Web terminal policy commits a provisional bubble only when
                # complete assistant text has actually crossed this boundary.
                ctx.mark_visible_reply()
            # feat-439-M2: 整轮每回合各带一段思考(决策 4 / §1 事实 A)。空正文「且无
            # 思考」的回合仍整段丢弃(避免空气泡)；空正文「但有思考」的回合不再丢，作为
            # 「过程项」转发到当前气泡(不 roll 新气泡、不发空 delta)。思考段的时序序号
            # 由 IM 持久化边界赋予(思考与工具共享一个 per-message 单调递增、按到达序的
            # 唯一序号)，gateway 不算 seq、只负责把 reasoning 转发到正确的目标气泡。
            reasoning = str(event.get("reasoning_content") or "").strip()
            group_id = str(event.get("group_id") or "").strip()
            visible_reasoning = _next_visible_reasoning(
                rid=run_id,
                group_id=group_id,
                reasoning=reasoning,
            )
            if not content and not visible_reasoning:
                return None
            # feat-393 heartbeat lazy-bubble path:
            # When to_user_id is set and no bubble exists yet, this is the first real
            # content event.  Gate on NO_REPLY: if agent chose to be quiet → stay silent.
            # Otherwise fire turn_start{to_user_id}, get back the resolved conversation_id
            # and message_id, store them, then emit the delta so streaming starts.
            if to_user_id and not message_id:
                # feat-439-M2: heartbeat 仅由正文驱动建泡；纯思考回合对 heartbeat 无
                # 可投递内容(也无气泡可挂)，直接跳过。
                if not content:
                    return None
                if is_protocol_silence_token(content):
                    # NO_REPLY: heartbeat has nothing to report; do not create any IM trace.
                    return None

                async def _heartbeat_lazy_turn_start(
                    mgr: IMConnectionManager = manager,
                    rid: str = run_id,
                    aid: str = agent_id,
                    uid: str = to_user_id,
                    text: str = content,
                    reasoning_text: str = visible_reasoning,
                    reasoning_group_id: str = group_id,
                    full_reasoning: str = reasoning,
                    new_kernel_id: str = kernel_msg_id,
                    delta_key: str | None = delta_idempotency_key,
                ) -> None:
                    try:
                        ack = await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            {
                                "kind": "turn_start",
                                "to_user_id": uid,
                                "agent_id": aid,
                                "run_id": rid,
                                "shadow_message_id": ctx.shadow_message_id,
                            },
                        )
                        ack_payload = (
                            ack.get("payload")
                            if isinstance(ack.get("payload"), dict)
                            else ack
                        )
                        returned_msg_id = (
                            ack_payload.get("message_id")
                            if isinstance(ack_payload, dict)
                            else None
                        )
                        returned_conv_id = (
                            ack_payload.get("conversation_id")
                            if isinstance(ack_payload, dict)
                            else None
                        )
                        skipped_reason = (
                            ack_payload.get("skipped")
                            if isinstance(ack_payload, dict)
                            else None
                        )
                        if skipped_reason:
                            # feat-393 fix-r1: IM skipped delivery (e.g. owner_unresolved).
                            # Per design decision-6: delivery failure ≠ run failure; log and
                            # let this heartbeat run finish normally — no exception, no retry.
                            import logging as _obs_logging  # noqa: PLC0415

                            _obs_logging.getLogger(__name__).warning(
                                "heartbeat delivery skipped for run_id=%s agent=%s: %s",
                                rid,
                                aid,
                                skipped_reason,
                            )
                            return
                        live_ctx = _live_context(run_context_store, rid)
                        if live_ctx is not None:
                            live_ctx.backfill_turn_start_ack(
                                message_id=(
                                    str(returned_msg_id) if returned_msg_id else None
                                ),
                                conversation_id=(
                                    str(returned_conv_id) if returned_conv_id else None
                                ),
                                kernel_message_id=new_kernel_id,
                            )
                        if returned_msg_id:
                            if reasoning_text:
                                await mgr.send_json(
                                    "node.streaming_delta",
                                    {
                                        "kind": "thinking_segment",
                                        "message_id": str(returned_msg_id),
                                        "text": reasoning_text,
                                        "run_id": rid,
                                        "process_seq": shadow_process_seq,
                                    },
                                )
                                _mark_visible_reasoning(
                                    rid=rid,
                                    group_id=reasoning_group_id,
                                    reasoning=full_reasoning,
                                )
                            await mgr.send_json(
                                "node.streaming_delta",
                                {
                                    "kind": "message_delta",
                                    "message_id": str(returned_msg_id),
                                    "delta_text": text,
                                    "run_id": rid,
                                    "idempotency_key": delta_key,
                                },
                            )
                    except Exception:  # noqa: BLE001
                        pass

                return _heartbeat_lazy_turn_start()

            # Detect a new assistant message within the same run (e.g. textA → tool_calls → textB).
            # The kernel's while-loop generates a fresh assistant_msg_id per iteration; when it
            # differs from the previous one we must close the old IM message and start a new one
            # so the frontend renders textA and textB as separate bubbles.
            # feat-439-M2: 多气泡 roll 只由「正文」触发——纯思考回合(content="")绝不 roll
            # 新气泡(否则会冒出空正文气泡)；它的思考随当前气泡走(见下方 if message_id)。
            # 本回合的 reasoning 随 roll 后的新气泡一起转发(它属于产出 textB 的那一回合)。
            if (
                content
                and kernel_msg_id
                and prev_kernel_msg_id
                and kernel_msg_id != prev_kernel_msg_id
            ):

                async def _close_old_and_restart(
                    mgr: IMConnectionManager = manager,
                    rid: str = run_id,
                    cid: str = conversation_id,
                    aid: str = agent_id,
                    old_msg_id: str = message_id,
                    text: str = content,
                    reasoning_text: str = visible_reasoning,
                    reasoning_group_id: str = group_id,
                    full_reasoning: str = reasoning,
                    new_kernel_id: str = kernel_msg_id,
                    delta_key: str | None = delta_idempotency_key,
                ) -> None:
                    new_msg_id: str | None = None
                    try:
                        old_text = ctx.external_current_text
                        _mirror_external_reply(
                            rid=rid,
                            ctx=ctx,
                            phase="intermediate",
                            text=old_text,
                        )
                        new_msg_id = await roll_bubble(
                            mgr,
                            run_id=rid,
                            conversation_id=cid,
                            agent_id=aid,
                            run_context_store=run_context_store,
                            old_message_id=old_msg_id,
                            new_kernel_message_id=new_kernel_id,
                            new_shadow_message_id=ctx.shadow_message_id,
                            old_elapsed_ms=(
                                rolled_shadow_snapshot.elapsed_ms
                                if rolled_shadow_snapshot is not None
                                else None
                            ),
                        )
                        if (
                            rolled_shadow_snapshot is not None
                            and shadow_bubble_reconcile is not None
                        ):
                            try:
                                await _reconcile_ready_snapshot(rolled_shadow_snapshot)
                            except Exception as exc:  # noqa: BLE001
                                _log.warning(
                                    "IM observer prior bubble reconcile failed; "
                                    "continuing new live bubble: %s",
                                    exc,
                                )
                        if new_msg_id:
                            # roll_bubble intentionally clears bubble-local visibility.
                            # This branch already has real text for the newly opened
                            # bubble, so restore the marker before the run terminal
                            # decides whether that bubble should be discarded.
                            ctx.mark_visible_reply()
                            ctx.record_assistant_text(text)
                            if reasoning_text:
                                await mgr.send_json(
                                    "node.streaming_delta",
                                    {
                                        "kind": "thinking_segment",
                                        "message_id": new_msg_id,
                                        "text": reasoning_text,
                                        "run_id": rid,
                                        "process_seq": shadow_process_seq,
                                    },
                                )
                                _mark_visible_reasoning(
                                    rid=rid,
                                    group_id=reasoning_group_id,
                                    reasoning=full_reasoning,
                                )
                            await mgr.send_json(
                                "node.streaming_delta",
                                {
                                    "kind": "message_delta",
                                    "message_id": new_msg_id,
                                    "delta_text": text,
                                    "run_id": rid,
                                    "idempotency_key": delta_key,
                                },
                            )
                    except Exception as exc:  # noqa: BLE001
                        live_ctx = _live_context(run_context_store, rid)
                        if live_ctx is not None:
                            if new_msg_id is None:
                                live_ctx.clear_message_id()
                            live_ctx.record_assistant_text(
                                text, kernel_message_id=new_kernel_id
                            )
                        if rolled_shadow_snapshot is not None:
                            _notify_shadow_pending()
                        _log.warning(
                            "IM observer close/restart delta send failed: %s", exc
                        )

                return _close_old_and_restart()

            if message_id:
                # feat-439-M2: 思考过程项先于正文 delta 转发到当前气泡。纯思考回合
                # (content="") 只发 thinking_segment，不发 delta、不动 kernel_message_id
                # (保留下一含正文回合的 roll 判定基准)。
                if content:
                    # turn_start already ack'd — send delta directly.
                    ctx.record_assistant_text(content, kernel_message_id=kernel_msg_id)
                if shadow_snapshot is not None:

                    async def _send_ordered_shadow_process(
                        mgr: IMConnectionManager = manager,
                    ) -> None:
                        if visible_reasoning:
                            await mgr.send_json(
                                "node.streaming_delta",
                                {
                                    "kind": "thinking_segment",
                                    "message_id": message_id,
                                    "text": visible_reasoning,
                                    "run_id": run_id,
                                    "process_seq": shadow_process_seq,
                                },
                            )
                            _mark_visible_reasoning(
                                rid=run_id, group_id=group_id, reasoning=reasoning
                            )
                        if content:
                            await mgr.send_json(
                                "node.streaming_delta",
                                {
                                    "kind": "message_delta",
                                    "message_id": message_id,
                                    "delta_text": content,
                                    "run_id": run_id,
                                    "idempotency_key": delta_idempotency_key,
                                },
                            )

                    return _send_ordered_shadow_process()
                if visible_reasoning:
                    task_tracker.start(
                        _send(
                            manager,
                            "node.streaming_delta",
                            {
                                "kind": "thinking_segment",
                                "message_id": message_id,
                                "text": visible_reasoning,
                                "run_id": run_id,
                                "process_seq": shadow_process_seq,
                            },
                        ),
                        name=f"thinking-segment:{run_id}",
                        run_id=run_id,
                    )
                    _mark_visible_reasoning(
                        rid=run_id, group_id=group_id, reasoning=reasoning
                    )
                if content:
                    task_tracker.start(
                        _send(
                            manager,
                            "node.streaming_delta",
                            {
                                "kind": "message_delta",
                                "message_id": message_id,
                                "delta_text": content,
                                "run_id": run_id,
                                "idempotency_key": delta_idempotency_key,
                            },
                        ),
                        name=f"message-delta:{run_id}",
                        run_id=run_id,
                    )
            elif content and conversation_id and agent_id:
                # Kernel skipped run_status=running; send turn_start inline and await ack
                # so we have message_id before the delta frame is dispatched.
                async def _turn_start_then_delta(
                    mgr: IMConnectionManager = manager,
                    rid: str = run_id,
                    cid: str = conversation_id,
                    aid: str = agent_id,
                    text: str = content,
                    reasoning_text: str = visible_reasoning,
                    reasoning_group_id: str = group_id,
                    full_reasoning: str = reasoning,
                    new_kernel_id: str = kernel_msg_id,
                    delta_key: str | None = delta_idempotency_key,
                ) -> None:
                    live_ctx = _live_context(run_context_store, rid)
                    if live_ctx is not None:
                        live_ctx.clear_message_id()
                        live_ctx.record_assistant_text(
                            text, kernel_message_id=new_kernel_id
                        )
                    try:
                        ack = await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            {
                                "kind": "turn_start",
                                "conversation_id": cid,
                                "agent_id": aid,
                                "run_id": rid,
                                "shadow_message_id": ctx.shadow_message_id,
                            },
                        )
                        returned_msg_id = extract_ack_message_id(ack)
                        live_ctx = _live_context(run_context_store, rid)
                        if returned_msg_id and live_ctx is not None:
                            live_ctx.backfill_turn_start_ack(message_id=returned_msg_id)
                            # feat-439-M2: 思考过程项先于正文 delta 转发到新建气泡。
                            if reasoning_text:
                                await mgr.send_json(
                                    "node.streaming_delta",
                                    {
                                        "kind": "thinking_segment",
                                        "message_id": returned_msg_id,
                                        "text": reasoning_text,
                                        "run_id": rid,
                                        "process_seq": shadow_process_seq,
                                    },
                                )
                                _mark_visible_reasoning(
                                    rid=rid,
                                    group_id=reasoning_group_id,
                                    reasoning=full_reasoning,
                                )
                            await mgr.send_json(
                                "node.streaming_delta",
                                {
                                    "kind": "message_delta",
                                    "message_id": returned_msg_id,
                                    "delta_text": text,
                                    "run_id": rid,
                                    "idempotency_key": delta_key,
                                },
                            )
                    except Exception as exc:  # noqa: BLE001
                        _log.warning(
                            "IM observer turn_start_then_delta send failed: %s", exc
                        )

                return _turn_start_then_delta()

        elif event_name == "turn_end":
            # bugfix-380 R3: completed=False = ModelError path.
            # Send message_completed with delivery_status="failed" to finalize the bubble
            # (error content was already sent via message_delta; final_content=None preserves it).
            # completed=True = normal success path, delivery_status defaults to "completed".
            turn_completed = event.get("completed") is not False

            # bugfix-410-fix-r1: turn_end is the normal-completion terminus (no reconcile
            # runs on this path), so reap any leftover per-run in-flight entry here as a
            # backstop. tool_end already drops entries as calls close; this catches the
            # empty-dict residue and guarantees the map can't grow unbounded on a long
            # Gateway. reconcile owns the abnormal path and pops there.
            running_tool_calls.pop(run_id, None)

            discard_reason = None
            if ctx.discard_current_bubble:
                discard_reason = "no_reply_token"
            elif (
                turn_completed
                and ctx.discard_empty_completion
                and not ctx.visible_reply_committed
            ):
                discard_reason = "empty_visible_reply"
            if message_id and discard_reason:

                async def _discard_and_finish() -> None:
                    try:
                        await _send(
                            manager,
                            "node.streaming_delta",
                            {
                                "kind": "message_discarded",
                                "message_id": message_id,
                                "run_id": run_id,
                                "reason": discard_reason,
                            },
                        )
                    finally:
                        _finish_shadow_live_run(manager, rid=run_id)

                return _discard_and_finish()

            token_usage_payload = _turn_token_usage(
                event, turn_completed=turn_completed
            )
            if message_id:
                _mirror_external_reply(
                    rid=run_id,
                    ctx=ctx,
                    phase="final",
                    text=ctx.external_current_text,
                )
                completion_kernel_message_id = ctx.kernel_message_id

                async def _complete_and_reconcile(
                    mgr: IMConnectionManager = manager,
                    snapshot: ExternalShadowBubble | None = shadow_snapshot,
                    kernel_message_id: str | None = completion_kernel_message_id,
                ) -> None:
                    try:
                        completion_payload = {
                            "kind": "message_completed",
                            "message_id": message_id,
                            "final_content": None,
                            "token_usage": token_usage_payload,
                            "delivery_status": "completed"
                            if turn_completed
                            else "failed",
                            # feat-445-M1: stamp the final bubble with the kernel message
                            # id that produced it (decision 4 fork anchor).
                            "kernel_message_id": kernel_message_id,
                            "run_id": run_id,
                            "elapsed_ms": snapshot.elapsed_ms
                            if snapshot is not None
                            else None,
                        }
                        if snapshot is None:
                            await mgr.send_json(
                                "node.streaming_delta", completion_payload
                            )
                        else:
                            await mgr.send_json_await_ack(
                                "node.streaming_delta", completion_payload
                            )
                        if (
                            snapshot is not None
                            and snapshot.state == "ready"
                            and shadow_bubble_reconcile is not None
                        ):
                            await _reconcile_ready_snapshot(snapshot)
                    except Exception as exc:  # noqa: BLE001
                        if snapshot is not None:
                            _notify_shadow_pending()
                        _log.warning("IM observer completion/reconcile failed: %s", exc)
                    finally:
                        _finish_shadow_live_run(mgr, rid=run_id)

                task_tracker.start(
                    _complete_and_reconcile(),
                    name=f"message-completed:{run_id}",
                    run_id=run_id,
                )
                return None
            if (
                shadow_snapshot is not None
                and shadow_snapshot.state == "ready"
                and im_connected
                and shadow_bubble_reconcile is not None
            ):
                task_tracker.start(
                    _reconcile_ready_snapshot(shadow_snapshot),
                    name=f"shadow-agent-reconcile:{run_id}",
                    run_id=run_id,
                )
            _finish_shadow_live_run(manager, rid=run_id)

    def _handle_process_event(
        scope: _DeliveryEventScope,
    ) -> Coroutine[Any, Any, None] | None:
        """Handle liveness, tool, and permission delivery events."""

        event = scope.event
        manager = scope.manager
        run_id = scope.run_id
        ctx = scope.ctx
        event_name = scope.event_name
        message_id = scope.message_id
        im_connected = scope.im_connected
        shadow_snapshot = scope.shadow_snapshot
        shadow_process_seq = scope.shadow_process_seq

        if event_name == "run_heartbeat":
            # bugfix-417-M3 R4: forward the kernel liveness heartbeat (tool / LLM-await /
            # parked-permission) to IM as a lightweight `run_heartbeat` delta. IM's
            # EventBridge appends a conversation_events row, advancing the message's
            # last_evt timestamp so the relay watchdog sees the run as alive — no
            # permission-specific marker needed (decision 4). Pure liveness: it does not
            # mutate message content or tool_calls and is not rendered by the frontend.
            if message_id:
                task_tracker.start(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "run_heartbeat",
                            "message_id": message_id,
                            "run_id": run_id,
                            "source": str(event.get("source") or ""),
                        },
                    ),
                    name=f"run-heartbeat:{run_id}",
                    run_id=run_id,
                )

        elif event_name == "tool_start":
            call_id = str(event.get("call_id") or "").strip() or run_id
            tool_name = str(event.get("name") or "")
            arguments = event.get("arguments") or {}
            if tool_name == "Workflow":
                ctx.mark_visible_reply()
                if workflow_permission_bindings is not None and ctx.kernel_session_id:
                    workflow_permission_bindings.register_pre_anchor(
                        WorkflowPermissionDeliveryAnchor(
                            parent_session_id=ctx.kernel_session_id,
                            parent_run_id=run_id,
                            parent_tool_call_id=call_id,
                            conversation_id=ctx.conversation_id,
                            message_id=ctx.message_id,
                            external_metadata=_external_context_metadata(ctx) or {},
                        )
                    )
            # feat-425 C1: tool_start SSE 已带 presentation.emoji(realtime_stream
            # on_tool_call)。透传到 running 行,自定义工具在执行阶段折叠行就显自带 emoji,
            # 不再回退 🔧、等完成才跳变。空串则省略(沿用 detail 的省略未设约定)。
            start_pres = event.get("presentation")
            start_emoji: str | None = None
            start_output: str | None = None
            start_detail: Any = None
            if isinstance(start_pres, Mapping) and start_pres.get("emoji"):
                start_emoji = str(start_pres["emoji"])
            if isinstance(start_pres, Mapping):
                if start_pres.get("summary"):
                    start_output = str(start_pres["summary"])
                start_detail = start_pres.get("detail")
            # bugfix-410-M2 R3: remember this call as in-flight until tool_end.
            # bugfix-416 #111 stores the original input; bugfix-441-M2 stores the
            # parameter-side presentation too, so abnormal reconcile can re-emit the
            # same refresh/historical payload the running row already showed.
            running_call: dict[str, Any] = {
                "name": tool_name,
                "input": arguments if isinstance(arguments, dict) else {},
            }
            if start_output is not None:
                running_call["output"] = start_output
            if start_detail is not None:
                running_call["detail"] = start_detail
            if start_emoji is not None:
                running_call["emoji"] = start_emoji
            running_tool_calls.setdefault(run_id, {})[call_id] = running_call
            if message_id:
                start_tool_call: dict[str, Any] = {
                    "id": call_id,
                    "name": tool_name,
                    "status": "running",
                    "input": arguments if isinstance(arguments, dict) else {},
                }
                if start_output is not None:
                    start_tool_call["output"] = start_output
                if start_detail is not None:
                    start_tool_call["detail"] = start_detail
                if start_emoji is not None:
                    start_tool_call["emoji"] = start_emoji
                start_payload = {
                    "kind": "tool_call_upserted",
                    "message_id": message_id,
                    "tool_call": start_tool_call,
                    "run_id": run_id,
                    "process_seq": shadow_process_seq,
                }
                if shadow_snapshot is not None:
                    return _send(manager, "node.streaming_delta", start_payload)
                task_tracker.start(
                    _send(
                        manager,
                        "node.streaming_delta",
                        start_payload,
                    ),
                    name=f"tool-start:{run_id}:{call_id}",
                    run_id=run_id,
                )

        elif event_name == "tool_end":
            call_id = str(event.get("call_id") or "").strip() or run_id
            tool_name = str(event.get("name") or "")
            arguments = event.get("arguments") or {}
            if tool_name == "Workflow":
                ctx.mark_visible_reply()
                event_metadata = event.get("event_metadata")
                if (
                    workflow_permission_bindings is not None
                    and isinstance(event_metadata, Mapping)
                    and event_metadata.get("parent_session_id") == ctx.kernel_session_id
                    and event_metadata.get("parent_run_id") == run_id
                    and event_metadata.get("parent_tool_call_id") == call_id
                ):
                    workflow_run_id = str(
                        event_metadata.get("workflow_run_id") or ""
                    ).strip()
                    deliveries = workflow_permission_bindings.bind_run(
                        parent_session_id=ctx.kernel_session_id,
                        parent_tool_call_id=call_id,
                        workflow_run_id=workflow_run_id,
                    )
                    _dispatch_workflow_permission_deliveries(deliveries)
            # bugfix-410-M2 R3: this call closed normally — drop it from in-flight.
            # bugfix-410-fix-r1: also drop the run_id entry once its last in-flight call
            # closes, so the per-run dict can't accumulate empty leftovers on a long-lived
            # Gateway (turn_end finalizes the bubble but never re-touches this map).
            inner = running_tool_calls.get(run_id)
            if inner is not None:
                inner.pop(call_id, None)
                if not inner:
                    running_tool_calls.pop(run_id, None)
            duration_ms = event.get("duration_ms")
            status = "failed" if event.get("error") else "completed"
            # bugfix-410-M2 R4 (#97): forward the badge classification (e.g. "denied"
            # for a hook-blocked tool) so the IM badge can render the right label.
            reason_code = event.get("reason_code")
            reason = str(reason_code).strip() if isinstance(reason_code, str) else None
            # feat-434-M1: forward the user-decision verdict (user_allow/user_deny)
            # the same way as reason — top-level kernel field, pure passthrough. None
            # for auto-allowed /普通工具 (gate region stays hidden downstream).
            approval_raw = event.get("approval")
            approval = (
                str(approval_raw).strip()
                if isinstance(approval_raw, str) and approval_raw
                else None
            )
            # feat-409 failalign: output(折叠行文案)只放 presenter 的干净 summary。
            # 不再前缀原始 event.error——presenter 失败态 summary 已是干净主参数,error
            # 只透传在 detail 里供展开卡渲染一次。早先把 error 也 append 进 output_parts
            # 并 `|` 拼接,导致折叠行重复出现 error(用户实测:read 失败 error 现两次)。
            pres = event.get("presentation")
            output: str | None = None
            detail: Any = None
            emoji: str | None = None
            if isinstance(pres, Mapping):
                if pres.get("summary"):
                    output = str(pres["summary"])
                # feat-409 决策 1: forward the presenter-produced structured detail
                # verbatim (already bounded by the kernel 256KB cap). The Gateway is a
                # pure passthrough pipe — no re-truncation, no per-tool restructuring.
                detail = pres.get("detail")
                # feat-425 决策 1/2: 原样转发 presenter 自带的 emoji(纯透传,不加工)。
                # 空串 = 工具未声明,沿用 detail 的省略未设约定,前端按名表兜底。
                if pres.get("emoji"):
                    emoji = str(pres["emoji"])
            tool_call_payload: dict[str, Any] = {
                "id": call_id,
                "name": tool_name,
                "status": status,
                # bugfix-410-M2 R4 (#97): forward the badge classification alongside
                # feat-409's structured detail — both ride the same tool_call payload.
                "reason": reason,
                "input": arguments if isinstance(arguments, dict) else {},
                "output": output,
                "duration_ms": int(duration_ms)
                if isinstance(duration_ms, (int, float))
                else None,
            }
            if detail is not None:
                tool_call_payload["detail"] = detail
            if emoji is not None:
                tool_call_payload["emoji"] = emoji
            # feat-434-M1 (F3): conditional write mirroring the emoji template —
            # only user-decided calls carry approval, so普通工具的 WS delta 不再带
            # `"approval": null`. Keeps both ends (Gateway forward / IM serialize)
            # consistent on the `if approval is not None` convention.
            if approval is not None:
                tool_call_payload["approval"] = approval
            if message_id:
                terminal_payload = {
                    "kind": "tool_call_completed",
                    "message_id": message_id,
                    "tool_call": tool_call_payload,
                    "run_id": run_id,
                    "process_seq": shadow_process_seq,
                }
                if shadow_snapshot is not None:
                    return _send(manager, "node.streaming_delta", terminal_payload)
                task_tracker.start(
                    _send(
                        manager,
                        "node.streaming_delta",
                        terminal_payload,
                    ),
                    name=f"tool-terminal:{run_id}:{call_id}",
                    run_id=run_id,
                )

        elif event_name == "permission_request":
            if event.get("workflow_run_id") and event.get("agent_call_id"):
                return None
            # Agent auto_mode_gate is awaiting a user decision; forward to IM so the
            # permission card can be rendered in the chat. External channels receive
            # the same request payload as a native surface (e.g. Feishu interactive
            # card) and resolve through the same kernel broker.
            request_id = str(event.get("request_id") or "").strip()
            tool_name = str(event.get("tool_name") or "").strip()
            tool_input = event.get("tool_input")
            question = str(event.get("question") or "").strip()
            options_raw = event.get("options")
            options = list(options_raw) if isinstance(options_raw, list) else []
            permission_request = {
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_input": dict(tool_input)
                if isinstance(tool_input, Mapping)
                else (tool_input or {}),
                "question": question,
                "options": options,
                "status": "pending",
            }
            if message_id and im_connected and manager is not None:
                task_tracker.start(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "permission_request",
                            "message_id": message_id,
                            "permission_request": permission_request,
                            "run_id": run_id,
                        },
                    ),
                    name=f"permission-request:{run_id}:{request_id}",
                    run_id=run_id,
                )
            _mirror_external_permission_request(
                rid=run_id,
                ctx=ctx,
                request=permission_request,
            )

        elif event_name == "permission_resolved":
            if event.get("workflow_run_id") and event.get("agent_call_id"):
                return None
            # Agent resolved a permission request (hook resumed); update the IM card
            # so the user sees the final decision.
            request_id = str(event.get("request_id") or "").strip()
            decision = str(event.get("decision") or "").strip()
            if message_id and im_connected and manager is not None:
                task_tracker.start(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "permission_resolved",
                            "message_id": message_id,
                            "request_id": request_id,
                            "decision": decision,
                            "run_id": run_id,
                        },
                    ),
                    name=f"permission-resolved:{run_id}:{request_id}",
                    run_id=run_id,
                )
            _mirror_external_permission_resolved(
                ctx=ctx,
                request_id=request_id,
                decision=decision,
            )

    def _handle_terminal_or_steer_event(
        scope: _DeliveryEventScope,
    ) -> Coroutine[Any, Any, None] | None:
        """Handle bubble rolls and abnormal terminal reconciliation."""

        event = scope.event
        manager = scope.manager
        run_id = scope.run_id
        ctx = scope.ctx
        event_name = scope.event_name
        conversation_id = scope.conversation_id
        message_id = scope.message_id
        agent_id = scope.agent_id
        rolled_shadow_snapshot = scope.rolled_shadow_snapshot
        shadow_snapshot = scope.shadow_snapshot
        abnormal_inflight = scope.abnormal_inflight

        if event_name == "injection_consumed":
            # bugfix-426-M4 决策6: the kernel just drained a steered (injected) message
            # into the model context on THIS run (run_id unchanged under 决策5). IM is a
            # time-ordered bubble chat: the steer user message already sits in the
            # conversation, so the reply to it must land in a NEW bubble that sorts
            # AFTER the steer — not appended to the bubble that was answering the prior
            # message. Finalize the current bubble A cleanly (completed, NOT failed —
            # the prior reply genuinely ended), then open bubble B at this consume
            # moment (so it sorts after the steer) and route subsequent deltas to it.
            # This is the same close+turn_start+restart sequence as the textA→textB
            # multi-bubble path (_close_old_and_restart), but anchored to the explicit
            # consume signal instead of inferring it from a changed kernel_message_id.
            # V3: do NOT gate on message_id. With V1's fix the active run's bubble
            # context survives, so message_id is normally present; but in the narrow
            # window where a turn_start ack has not returned yet, message_id can be ""
            # transiently. Still roll: _roll_bubble closes bubble A only if there is one
            # (old_message_id truthy) and always opens B, so the steer reply never gets
            # stranded without a bubble. _roll_bubble's per-run guard makes back-to-back
            # steers (two injection_consumed) safe (no double-open / zombie bubble).
            if conversation_id and agent_id:

                async def _roll_bubble_on_steer(
                    mgr: IMConnectionManager = manager,
                    rid: str = run_id,
                    cid: str = conversation_id,
                    aid: str = agent_id,
                    old_msg_id: str = message_id,
                    consumed_returns: list[dict[str, Any]] = [
                        dict(item)
                        for item in event.get("background_returns", [])
                        if isinstance(item, Mapping)
                    ]
                    if isinstance(event.get("background_returns"), list)
                    else [],
                ) -> None:
                    reconcile_started = False
                    new_message_id: str | None = None
                    try:
                        new_message_id = await roll_bubble(
                            mgr,
                            run_id=rid,
                            conversation_id=cid,
                            agent_id=aid,
                            run_context_store=run_context_store,
                            old_message_id=old_msg_id or None,
                            # Clear kernel_message_id (new_kernel_message_id=None) so the
                            # next assistant_message delta streams straight into bubble B
                            # rather than tripping _close_old_and_restart again.
                            new_kernel_message_id=None,
                            new_shadow_message_id=ctx.shadow_message_id,
                            old_elapsed_ms=(
                                rolled_shadow_snapshot.elapsed_ms
                                if rolled_shadow_snapshot is not None
                                else None
                            ),
                            background_returns=consumed_returns,
                        )
                        if new_message_id is None:
                            _clear_live_bubble_context(
                                rid=rid, clear_conversation=False
                            )
                        if (
                            rolled_shadow_snapshot is not None
                            and shadow_bubble_reconcile is not None
                        ):
                            reconcile_started = True
                            await _reconcile_ready_snapshot(rolled_shadow_snapshot)
                    except Exception as exc:  # noqa: BLE001
                        if not reconcile_started:
                            _clear_live_bubble_context(
                                rid=rid, clear_conversation=False
                            )
                        if rolled_shadow_snapshot is not None and not reconcile_started:
                            _notify_shadow_pending()
                        _log.warning("IM observer steer bubble roll failed: %s", exc)

                return _roll_bubble_on_steer()

        elif event_name == "run_terminal_reconcile":
            # bugfix-410-M2 R3 (#97): a run terminated abnormally (watchdog timeout /
            # crash / interrupt) and any tool_call still in flight never received a
            # tool_end, so its IM badge would spin forever. Close each remaining
            # in-flight call with status=failed + a reason. Already-completed calls
            # were popped on tool_end, so they are untouched. reason ∈ {stalled
            # (watchdog liveness reap → 已中断), interrupted (other abnormal
            # termination → 已中断), tool_timeout (tool's own deadline → 执行超时)}.
            reason = str(event.get("reason") or "interrupted").strip() or "interrupted"
            # bugfix-417-M5 (#114): a user /stop attaches the CC-identical
            # user-attribution content so the in-flight tool card displays the same
            # body the model sees in the transcript. Absent (system reap) → no body.
            reconcile_content = event.get("content")
            reconcile_output = (
                str(reconcile_content)
                if isinstance(reconcile_content, str) and reconcile_content
                else None
            )
            terminal_frames: list[dict[str, Any]] = []
            if message_id and abnormal_inflight:
                for stuck_call_id, stuck_call in abnormal_inflight.items():
                    # bugfix-416 #111: re-emit the original input recorded at tool_start
                    # so command/description survive the reconcile; only status + reason
                    # change. (Entries pre-bugfix-416 stored a bare name string — tolerate
                    # that shape so an in-flight call across a deploy still closes cleanly.)
                    if isinstance(stuck_call, Mapping):
                        stuck_name = str(stuck_call.get("name") or "")
                        stuck_input = stuck_call.get("input") or {}
                        stuck_output = stuck_call.get("output")
                        stuck_detail = stuck_call.get("detail")
                        stuck_emoji = stuck_call.get("emoji")
                    else:
                        stuck_name = str(stuck_call)
                        stuck_input = {}
                        stuck_output = None
                        stuck_detail = None
                        stuck_emoji = None
                    stuck_tool_call: dict[str, Any] = {
                        "id": stuck_call_id,
                        "name": stuck_name,
                        "status": "failed",
                        "reason": reason,
                        # stuck_input is already a dict: the Mapping branch
                        # uses `or {}`, and the bare-name branch sets {}.
                        "input": stuck_input,
                    }
                    if stuck_output is not None:
                        stuck_tool_call["output"] = stuck_output
                    if stuck_detail is not None:
                        stuck_tool_call["detail"] = stuck_detail
                    if stuck_emoji is not None:
                        stuck_tool_call["emoji"] = stuck_emoji
                    if reconcile_output is not None:
                        stuck_tool_call["output"] = reconcile_output
                    process_seq = None
                    if shadow_snapshot is not None:
                        stored_call = next(
                            (
                                item
                                for item in shadow_snapshot.tool_calls
                                if item.get("id") == stuck_call_id
                            ),
                            None,
                        )
                        if stored_call is not None:
                            process_seq = stored_call.get("seq")
                    terminal_frame = {
                        "kind": "tool_call_completed",
                        "message_id": message_id,
                        "tool_call": stuck_tool_call,
                        "run_id": run_id,
                    }
                    if process_seq is not None:
                        terminal_frame["process_seq"] = process_seq
                    terminal_frames.append(terminal_frame)

            # bugfix-417-fix2 (#114, Issue 1): a user /stop cancels the run, but the
            # kernel emits NO turn_end on the cancel path (turn_end fires only on
            # success / ModelError), so the agent bubble would stay stuck on the
            # "running" spinner. Every abnormal terminal closes the current bubble:
            # user /stop is completed, while watchdog/crash/shutdown aborts are failed.
            # The coordinator supplies the status explicitly so a system abort cannot
            # be mistaken for a clean user cancellation.
            finalize_bubble = bool(event.get("finalize_bubble"))
            delivery_status = str(event.get("delivery_status") or "completed")

            async def _complete_abnormal_terminal(
                mgr: IMConnectionManager = manager,
                snapshot: ExternalShadowBubble | None = shadow_snapshot,
                frames: tuple[dict[str, Any], ...] = tuple(terminal_frames),
                live_message_id: str = message_id,
                kernel_message_id: str | None = ctx.kernel_message_id,
            ) -> None:
                try:
                    for frame in frames:
                        await mgr.send_json("node.streaming_delta", frame)
                    if finalize_bubble and live_message_id:
                        completion_payload: dict[str, Any] = {
                            "kind": "message_completed",
                            "message_id": live_message_id,
                            "final_content": None,
                            "token_usage": None,
                            "delivery_status": delivery_status,
                            "run_id": run_id,
                        }
                        if snapshot is not None:
                            completion_payload["kernel_message_id"] = kernel_message_id
                            completion_payload["elapsed_ms"] = snapshot.elapsed_ms
                            await mgr.send_json_await_ack(
                                "node.streaming_delta", completion_payload
                            )
                        else:
                            await mgr.send_json(
                                "node.streaming_delta", completion_payload
                            )
                    if snapshot is not None and snapshot.state == "ready":
                        await _reconcile_ready_snapshot(snapshot)
                except Exception as exc:  # noqa: BLE001
                    if snapshot is not None:
                        _notify_shadow_pending()
                    _log.warning("IM observer abnormal reconcile failed: %s", exc)
                finally:
                    _finish_shadow_live_run(mgr, rid=run_id)

            if (
                terminal_frames
                or (finalize_bubble and message_id)
                or (shadow_snapshot is not None and shadow_snapshot.state == "ready")
            ):
                # Legacy user-stop emitters set finalize_bubble without an explicit
                # status; preserve their clean-completion contract. New system-abort
                # emitters always carry delivery_status="failed".
                task_tracker.start(
                    _complete_abnormal_terminal(),
                    name=f"bubble-finalize:{run_id}",
                    run_id=run_id,
                )

    event_handlers: dict[
        str, Callable[[_DeliveryEventScope], Coroutine[Any, Any, None] | None]
    ] = {
        "run_status": _handle_bubble_event,
        "assistant_message": _handle_bubble_event,
        "turn_end": _handle_bubble_event,
        "run_heartbeat": _handle_process_event,
        "tool_start": _handle_process_event,
        "tool_end": _handle_process_event,
        "permission_request": _handle_process_event,
        "permission_resolved": _handle_process_event,
        "injection_consumed": _handle_terminal_or_steer_event,
        "run_terminal_reconcile": _handle_terminal_or_steer_event,
    }

    def observer(event: Mapping[str, Any]) -> "Coroutine[Any, Any, None] | None":
        """Dispatch one kernel event to its typed runtime-delivery event family."""

        prepared = _prepare_event(event)
        if prepared.handled:
            return prepared.result
        if prepared.scope is None:
            return None
        handler = event_handlers.get(prepared.scope.event_name)
        return handler(prepared.scope) if handler is not None else None

    return observer
