"""Translate kernel runtime events into Gateway delivery side effects."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Mapping
import logging
from typing import Any

from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.ws.im_connection import IMConnectionManager

from .context import RunDeliveryContextStore

_log = logging.getLogger("personal_assistant.gateway.runtime_delivery.observer")


def _run_context_map(
    run_context_store: dict[str, dict[str, str]] | RunDeliveryContextStore,
) -> dict[str, dict[str, str]]:
    if isinstance(run_context_store, RunDeliveryContextStore):
        return run_context_store.legacy_contexts
    return run_context_store


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
    run_context_store: dict[str, dict[str, str]] | RunDeliveryContextStore,
    old_message_id: str | None,
    new_kernel_message_id: str | None = None,
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
    context_map = _run_context_map(run_context_store)
    ctx = context_map.get(run_id)
    if ctx is None:
        return None
    if ctx.get("rolling"):
        # A roll is already in flight for this run; the in-flight one owns the
        # transition. Dropping this duplicate is safe — the steer's content still
        # streams into whatever bubble the in-flight roll lands on.
        return None
    ctx["rolling"] = "1"
    # feat-445-M1: the bubble being closed was produced by the kernel message tracked in
    # ctx["kernel_message_id"]; stamp it onto the closing frame so IM persists the
    # per-bubble id BEFORE the new bubble's id overwrites ctx (decision 4 fork anchor).
    old_kernel_message_id = ctx.get("kernel_message_id")
    try:
        if old_message_id:
            await manager.send_json(
                "node.streaming_delta",
                {
                    "kind": "message_completed",
                    "message_id": old_message_id,
                    "final_content": None,
                    "token_usage": None,
                    "delivery_status": "completed",
                    "kernel_message_id": old_kernel_message_id,
                    "run_id": run_id,
                },
            )
        ack = await manager.send_json_await_ack(
            "node.streaming_delta",
            {
                "kind": "turn_start",
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "run_id": run_id,
            },
        )
        new_message_id = extract_ack_message_id(ack)
        live_ctx = context_map.get(run_id)
        if new_message_id and live_ctx is not None:
            live_ctx["message_id"] = new_message_id
            if new_kernel_message_id:
                live_ctx["kernel_message_id"] = new_kernel_message_id
            else:
                live_ctx.pop("kernel_message_id", None)
            return new_message_id
        return None
    finally:
        live_ctx = context_map.get(run_id)
        if live_ctx is not None:
            live_ctx.pop("rolling", None)


def build_kernel_event_observer(
    *,
    im_connection_manager_factory: Callable[[], IMConnectionManager | None],
    run_context_store: dict[str, dict[str, str]] | RunDeliveryContextStore,
    running_tool_calls: dict[str, dict[str, dict[str, Any]]] | None = None,
    external_reply_sender: Callable[[str, Mapping[str, str]], Any] | None = None,
    external_permission_request_sender: (
        Callable[[Mapping[str, Any], Mapping[str, str]], Any] | None
    ) = None,
    external_permission_resolved_sender: (
        Callable[[str, str, Mapping[str, str]], Any] | None
    ) = None,
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
    - Normal chat (conversation_id present) is unchanged (eager placeholder on run_status=running).

    Canonical session (feat-394 decision 3):
    - HeartbeatScheduler.tick() calls session_store.find_direct_by_agent() BEFORE each run
      submission to update canonical_session_store — tick-time read, no ack dependency.
    """

    context_map = _run_context_map(run_context_store)

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
    visible_reasoning_by_group: dict[str, dict[str, str]] = {}

    async def _send(
        manager: IMConnectionManager, message_type: str, payload: Mapping[str, Any]
    ) -> None:
        try:
            await manager.send_json(message_type, payload)
        except Exception as exc:  # noqa: BLE001
            # IM send failure must not propagate into the event stream; log so the
            # drop is observable (refactor-395-M1).
            _log.warning("IM observer send failed for %s: %s", message_type, exc)

    def _is_external_reply_context(ctx: Mapping[str, str]) -> bool:
        return (
            external_reply_sender is not None
            and _external_context_metadata(ctx) is not None
        )

    def _external_context_metadata(ctx: Mapping[str, str]) -> dict[str, str] | None:
        channel_name = ctx.get("reply_channel_name") or ""
        target_chat_id = ctx.get("reply_target_chat_id") or ""
        if (
            ctx.get("trigger_source") == "im"
            or not channel_name
            or channel_name == "web_relay"
            or not target_chat_id
        ):
            return None
        metadata: dict[str, str] = {
            "channel_name": channel_name,
            "target_chat_id": target_chat_id,
        }
        optional_keys = ("reply_thread_id", "feishu_message_id")
        for key in optional_keys:
            value = ctx.get(key)
            if value:
                metadata[key] = value
        return metadata

    def _mirror_external_reply(
        *, rid: str, ctx: dict[str, str], phase: str, text: str
    ) -> None:
        if not _is_external_reply_context(ctx):
            return
        cleaned_text = text.strip()
        if not cleaned_text:
            return
        if InboundPipeline._is_no_reply_token(cleaned_text):
            return
        external_metadata = _external_context_metadata(ctx)
        if external_metadata is None:
            return
        bubble_key = (
            ctx.get("kernel_message_id")
            or ctx.get("message_id")
            or f"text:{cleaned_text}"
        )
        metadata: dict[str, str] = {
            "reply_phase": phase,
            "reply_dedupe_key": f"{rid}:bubble:{bubble_key}",
            **external_metadata,
        }
        result = external_reply_sender(cleaned_text, metadata)
        if asyncio.iscoroutine(result):
            asyncio.get_event_loop().create_task(result)

    def _mirror_external_permission_request(
        *, rid: str, ctx: Mapping[str, str], request: Mapping[str, Any]
    ) -> None:
        if external_permission_request_sender is None:
            return
        metadata = _external_context_metadata(ctx)
        if metadata is None:
            return
        metadata["run_id"] = rid
        result = external_permission_request_sender(request, metadata)
        if asyncio.iscoroutine(result):
            asyncio.get_event_loop().create_task(result)

    def _mirror_external_permission_resolved(
        *, ctx: Mapping[str, str], request_id: str, decision: str
    ) -> None:
        if external_permission_resolved_sender is None:
            return
        metadata = _external_context_metadata(ctx)
        if metadata is None:
            return
        result = external_permission_resolved_sender(request_id, decision, metadata)
        if asyncio.iscoroutine(result):
            asyncio.get_event_loop().create_task(result)

    def _mirror_external_current_as_intermediate(
        *, rid: str, ctx: dict[str, str]
    ) -> None:
        current_text = ctx.get("external_current_text") or ""
        if not current_text.strip():
            return
        marker = ctx.get("kernel_message_id") or f"text:{current_text.strip()}"
        if ctx.get("external_intermediate_sent_marker") == marker:
            return
        _mirror_external_reply(
            rid=rid,
            ctx=ctx,
            phase="intermediate",
            text=current_text,
        )
        ctx["external_intermediate_sent_marker"] = marker

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

    def observer(event: Mapping[str, Any]) -> "Coroutine[Any, Any, None] | None":
        manager = im_connection_manager_factory()
        run_id = str(event.get("run_id") or "").strip()
        if not run_id:
            return None
        ctx = context_map.get(run_id)
        if ctx is None:
            return None
        event_name = str(event.get("event") or "").strip()
        if event_name in {"turn_end", "run_terminal_reconcile"}:
            _clear_run_visible_reasoning(run_id)
        conversation_id = ctx.get("conversation_id") or ""
        message_id = ctx.get("message_id") or ""
        agent_id = ctx.get("agent_id") or ""

        # feat-393: heartbeat runs carry to_user_id instead of conversation_id.
        # The lazy-bubble gate: skip eager turn_start; defer to assistant_message.
        to_user_id = ctx.get("to_user_id") or ""

        im_connected = manager is not None and manager.connected
        has_external_context = _external_context_metadata(ctx) is not None
        if not im_connected and not has_external_context:
            return None
        if not im_connected:
            if event_name == "assistant_message":
                content = str(event.get("content") or "").strip()
                if not content:
                    return None
                kernel_msg_id = str(event.get("message_id") or "").strip()
                prev_kernel_msg_id = ctx.get("kernel_message_id") or ""
                if (
                    kernel_msg_id
                    and prev_kernel_msg_id
                    and kernel_msg_id != prev_kernel_msg_id
                ):
                    _mirror_external_current_as_intermediate(rid=run_id, ctx=ctx)
                if kernel_msg_id:
                    ctx["kernel_message_id"] = kernel_msg_id
                ctx["external_current_text"] = content
                return None
            if event_name in {"tool_start", "permission_request"}:
                _mirror_external_current_as_intermediate(rid=run_id, ctx=ctx)
                if event_name == "tool_start":
                    return None
            elif event_name == "turn_end":
                running_tool_calls.pop(run_id, None)
                return None
            elif event_name != "permission_resolved":
                return None
        loop = asyncio.get_event_loop()

        if event_name == "run_status" and event.get("status") == "running":
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
                        ack = await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            {
                                "kind": "turn_start",
                                "conversation_id": cid,
                                "agent_id": aid,
                                "run_id": rid,
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
                        if returned_msg_id and rid in context_map:
                            context_map[rid]["message_id"] = str(returned_msg_id)
                    except Exception as exc:  # noqa: BLE001
                        _log.warning("IM observer turn_start send/ack failed: %s", exc)

                return _send_turn_start_and_store()

        elif event_name == "assistant_message":
            content = str(event.get("content") or "").strip()
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
            kernel_msg_id = str(event.get("message_id") or "").strip()
            prev_kernel_msg_id = ctx.get("kernel_message_id") or ""

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
                from personal_assistant.gateway.inbound_pipeline import (
                    InboundPipeline as _IP,
                )

                if _IP._is_no_reply_token(content):
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
                ) -> None:
                    try:
                        ack = await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            {
                                "kind": "turn_start",
                                "to_user_id": uid,
                                "agent_id": aid,
                                "run_id": rid,
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
                        if returned_msg_id and rid in context_map:
                            context_map[rid]["message_id"] = str(returned_msg_id)
                        if returned_conv_id and rid in context_map:
                            context_map[rid]["conversation_id"] = str(
                                returned_conv_id
                            )
                        if new_kernel_id and rid in context_map:
                            context_map[rid]["kernel_message_id"] = new_kernel_id
                        if returned_msg_id:
                            if reasoning_text:
                                await mgr.send_json(
                                    "node.streaming_delta",
                                    {
                                        "kind": "thinking_segment",
                                        "message_id": str(returned_msg_id),
                                        "text": reasoning_text,
                                        "run_id": rid,
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
                ) -> None:
                    try:
                        old_text = ctx.get("external_current_text") or ""
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
                            run_context_store=context_map,
                            old_message_id=old_msg_id,
                            new_kernel_message_id=new_kernel_id,
                        )
                        if new_msg_id:
                            ctx["external_current_text"] = text
                            if reasoning_text:
                                await mgr.send_json(
                                    "node.streaming_delta",
                                    {
                                        "kind": "thinking_segment",
                                        "message_id": new_msg_id,
                                        "text": reasoning_text,
                                        "run_id": rid,
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
                                },
                            )
                    except Exception as exc:  # noqa: BLE001
                        _log.warning(
                            "IM observer close/restart delta send failed: %s", exc
                        )

                return _close_old_and_restart()

            if message_id:
                # feat-439-M2: 思考过程项先于正文 delta 转发到当前气泡。纯思考回合
                # (content="") 只发 thinking_segment，不发 delta、不动 kernel_message_id
                # (保留下一含正文回合的 roll 判定基准)。
                if visible_reasoning:
                    loop.create_task(
                        _send(
                            manager,
                            "node.streaming_delta",
                            {
                                "kind": "thinking_segment",
                                "message_id": message_id,
                                "text": visible_reasoning,
                                "run_id": run_id,
                            },
                        )
                    )
                    _mark_visible_reasoning(
                        rid=run_id, group_id=group_id, reasoning=reasoning
                    )
                if content:
                    # turn_start already ack'd — send delta directly.
                    if kernel_msg_id:
                        ctx["kernel_message_id"] = kernel_msg_id
                    ctx["external_current_text"] = content
                    loop.create_task(
                        _send(
                            manager,
                            "node.streaming_delta",
                            {
                                "kind": "message_delta",
                                "message_id": message_id,
                                "delta_text": content,
                                "run_id": run_id,
                            },
                        )
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
                ) -> None:
                    try:
                        ack = await mgr.send_json_await_ack(
                            "node.streaming_delta",
                            {
                                "kind": "turn_start",
                                "conversation_id": cid,
                                "agent_id": aid,
                                "run_id": rid,
                            },
                        )
                        returned_msg_id = extract_ack_message_id(ack)
                        if returned_msg_id and rid in context_map:
                            context_map[rid]["message_id"] = returned_msg_id
                            if new_kernel_id:
                                context_map[rid]["kernel_message_id"] = (
                                    new_kernel_id
                                )
                            context_map[rid]["external_current_text"] = text
                            # feat-439-M2: 思考过程项先于正文 delta 转发到新建气泡。
                            if reasoning_text:
                                await mgr.send_json(
                                    "node.streaming_delta",
                                    {
                                        "kind": "thinking_segment",
                                        "message_id": returned_msg_id,
                                        "text": reasoning_text,
                                        "run_id": rid,
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

            # Finalize message with token_usage if present (only on success path).
            usage_raw = event.get("usage") if turn_completed else None
            token_usage_payload: dict[str, object] | None = None
            if isinstance(usage_raw, Mapping):
                prompt = usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens")
                completion = usage_raw.get("completion_tokens") or usage_raw.get(
                    "output_tokens"
                )
                if isinstance(prompt, int) and isinstance(completion, int):
                    token_usage_payload = {
                        "prompt": prompt,
                        "completion": completion,
                        "total": prompt + completion,
                    }
                    cw = event.get("context_window")
                    if isinstance(cw, int) and cw > 0:
                        token_usage_payload["context_window"] = cw
                    # feat-439-M1: token_usage_payload 是白名单(只挑 prompt/completion)，
                    # 缓存命中两字段必须在此显式补带，否则永远到不了 IM、命中率恒 0%。
                    cache_read = usage_raw.get("cache_read_tokens")
                    cache_total_input = usage_raw.get("cache_total_input_tokens")
                    token_usage_payload["cache_read"] = (
                        cache_read if isinstance(cache_read, int) else 0
                    )
                    token_usage_payload["cache_total_input"] = (
                        cache_total_input if isinstance(cache_total_input, int) else 0
                    )
            if message_id:
                _mirror_external_reply(
                    rid=run_id,
                    ctx=ctx,
                    phase="final",
                    text=ctx.get("external_current_text") or "",
                )
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "message_completed",
                            "message_id": message_id,
                            "final_content": None,
                            "token_usage": token_usage_payload,
                            "delivery_status": "completed"
                            if turn_completed
                            else "failed",
                            # feat-445-M1: stamp the final bubble with the kernel message
                            # id that produced it (decision 4 fork anchor).
                            "kernel_message_id": ctx.get("kernel_message_id"),
                            "run_id": run_id,
                        },
                    )
                )

        elif event_name == "run_heartbeat":
            # bugfix-417-M3 R4: forward the kernel liveness heartbeat (tool / LLM-await /
            # parked-permission) to IM as a lightweight `run_heartbeat` delta. IM's
            # EventBridge appends a conversation_events row, advancing the message's
            # last_evt timestamp so the relay watchdog sees the run as alive — no
            # permission-specific marker needed (decision 4). Pure liveness: it does not
            # mutate message content or tool_calls and is not rendered by the frontend.
            if message_id:
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "run_heartbeat",
                            "message_id": message_id,
                            "run_id": run_id,
                            "source": str(event.get("source") or ""),
                        },
                    )
                )

        elif event_name == "tool_start":
            call_id = str(event.get("call_id") or "").strip() or run_id
            tool_name = str(event.get("name") or "")
            arguments = event.get("arguments") or {}
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
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "tool_call_upserted",
                            "message_id": message_id,
                            "tool_call": start_tool_call,
                            "run_id": run_id,
                        },
                    )
                )

        elif event_name == "tool_end":
            call_id = str(event.get("call_id") or "").strip() or run_id
            tool_name = str(event.get("name") or "")
            arguments = event.get("arguments") or {}
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
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "tool_call_completed",
                            "message_id": message_id,
                            "tool_call": tool_call_payload,
                            "run_id": run_id,
                        },
                    )
                )

        elif event_name == "permission_request":
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
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "permission_request",
                            "message_id": message_id,
                            "permission_request": permission_request,
                            "run_id": run_id,
                        },
                    )
                )
            _mirror_external_permission_request(
                rid=run_id,
                ctx=ctx,
                request=permission_request,
            )

        elif event_name == "permission_resolved":
            # Agent resolved a permission request (hook resumed); update the IM card
            # so the user sees the final decision.
            request_id = str(event.get("request_id") or "").strip()
            decision = str(event.get("decision") or "").strip()
            if message_id and im_connected and manager is not None:
                loop.create_task(
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
                    )
                )
            _mirror_external_permission_resolved(
                ctx=ctx,
                request_id=request_id,
                decision=decision,
            )

        elif event_name == "injection_consumed":
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
                ) -> None:
                    try:
                        await roll_bubble(
                            mgr,
                            run_id=rid,
                            conversation_id=cid,
                            agent_id=aid,
                            run_context_store=context_map,
                            old_message_id=old_msg_id or None,
                            # Clear kernel_message_id (new_kernel_message_id=None) so the
                            # next assistant_message delta streams straight into bubble B
                            # rather than tripping _close_old_and_restart again.
                            new_kernel_message_id=None,
                        )
                    except Exception as exc:  # noqa: BLE001
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
            inflight = running_tool_calls.pop(run_id, {})
            if message_id and inflight:
                for stuck_call_id, stuck_call in inflight.items():
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
                    loop.create_task(
                        _send(
                            manager,
                            "node.streaming_delta",
                            {
                                "kind": "tool_call_completed",
                                "message_id": message_id,
                                "tool_call": stuck_tool_call,
                                "run_id": run_id,
                            },
                        )
                    )

            # bugfix-417-fix2 (#114, Issue 1): a user /stop cancels the run, but the
            # kernel emits NO turn_end on the cancel path (turn_end fires only on
            # success / ModelError), so the agent bubble would stay stuck on the
            # "running" spinner. When the Gateway marks this reconcile finalize_bubble
            # (set ONLY for a user-/stop cancel, never for a watchdog/crash reap which
            # must stay failed — Req B), finalize the bubble with delivery_status=
            # completed (a user stop is a clean termination, not a failure).
            if event.get("finalize_bubble") and message_id:
                loop.create_task(
                    _send(
                        manager,
                        "node.streaming_delta",
                        {
                            "kind": "message_completed",
                            "message_id": message_id,
                            "final_content": None,
                            "token_usage": None,
                            "delivery_status": "completed",
                            "run_id": run_id,
                        },
                    )
                )

    return observer
