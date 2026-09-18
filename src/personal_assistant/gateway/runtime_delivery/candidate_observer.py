"""Collect complete model rounds before asking the Gateway to deliver them."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
import inspect
from typing import Any

from personal_assistant.gateway.message_delivery import DeliveryResult, ReplyCandidate
from personal_assistant.gateway.runtime_footer import (
    ExternalFinalProjection,
    TerminalFooterFacts,
)
from .context import RunDeliveryContextStore


@dataclass
class _Round:
    chunks: list[str] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)
    event: Mapping[str, Any] = field(default_factory=dict)
    background_returns: list[Mapping[str, Any]] = field(default_factory=list)


def _feedback(result: DeliveryResult) -> str:
    return (
        "<system-reminder>\n"
        + result.diagnostic
        + " It was withheld before publication and was never delivered to the "
        "conversation, so the participants have not received its content. "
        "Earlier successfully published assistant messages remain part of the "
        "shared conversation.\n\n"
        + result.continuation
        + " If a public response is warranted, include all information the "
        "recipients still need, since the withheld draft communicated nothing "
        "to them.\n</system-reminder>"
    )


def build_candidate_observer(
    *,
    writer: Callable[[Mapping[str, Any]], Any],
    context_store: RunDeliveryContextStore,
    deliver: Callable[[ReplyCandidate], Awaitable[DeliveryResult]],
    external_final_projection_builder: (
        Callable[[str, str, TerminalFooterFacts], ExternalFinalProjection] | None
    ) = None,
) -> Callable[[Mapping[str, Any]], Awaitable[None]]:
    """Separate model facts from complete, privately prepared delivery intents.

    Args:
        writer: Delivery owner's process event sink.
        context_store: Actual accepted run routing and lifecycle contexts.
        deliver: Sole Gateway entry point for complete automatic replies.
        external_final_projection_builder: Optional final external display policy.

    Returns:
        An awaited event consumer; chunk endings never authorize publication.
    """
    rounds: dict[tuple[str, str], _Round] = {}
    completed: dict[str, set[str]] = {}
    pending: dict[str, ReplyCandidate] = {}
    tool_activity: set[str] = set()

    async def forward(event: Mapping[str, Any]) -> None:
        result = writer(event)
        if inspect.isawaitable(result):
            await result

    async def publish(candidate: ReplyCandidate) -> None:
        context = context_store.get(candidate.run_id)
        if context is None:
            return
        result = await deliver(candidate)
        if result.state == "withheld":
            context.delivery_failed = True
            context.delivery_feedback = _feedback(result)
        elif result.state == "pending":
            context.delivery_failed = True
        elif result.state in {"delivered", "partial"}:
            context.delivery_published_text = (
                context.managed_reply_text or candidate.text
            )

    async def publish_pending(
        run_id: str, *, terminal_event: Mapping[str, Any] | None = None
    ) -> None:
        candidate = pending.pop(run_id, None)
        context = context_store.get(run_id)
        if candidate is None or context is None:
            return
        if terminal_event is not None:
            usage = terminal_event.get("usage")
            prompt_tokens = (
                usage.get("prompt_tokens") if isinstance(usage, Mapping) else None
            )
            if not isinstance(prompt_tokens, int):
                prompt_tokens = (
                    usage.get("input_tokens") if isinstance(usage, Mapping) else None
                )
            context_window = terminal_event.get("context_window")
            facts = TerminalFooterFacts(
                model=context.model or None,
                prompt_tokens=(
                    prompt_tokens if isinstance(prompt_tokens, int) else None
                ),
                context_window=(
                    context_window if isinstance(context_window, int) else None
                ),
            )
            context.terminal_footer_facts = facts
            context.external_final_projection = (
                external_final_projection_builder(
                    candidate.text, context.reply_channel_name, facts
                )
                if external_final_projection_builder is not None
                else ExternalFinalProjection(text=candidate.text)
            )
        await publish(candidate)

    async def observe(event: Mapping[str, Any]) -> None:
        run_id = str(event.get("run_id") or "")
        context = context_store.get(run_id)
        name = event.get("event")
        group_id = str(event.get("group_id") or "")
        if context is None:
            await forward(event)
            return
        if name == "injection_consumed":
            context_store.consume_inputs(run_id, list(event.get("pending_ids") or []))
            await publish_pending(run_id)
        if name == "gateway_message":
            # Product notices already have a complete body and stable identity.
            identity = str(event["message_id"])
            rounds[(run_id, identity)] = _Round(
                chunks=[str(event.get("content") or "")], event=event
            )
            group_id = identity
            name = "model_round_end"
            event = {**event, "completed": True}
        if name == "assistant_message":
            pending_candidate = pending.get(run_id)
            if pending_candidate is not None and pending_candidate.group_id != group_id:
                await publish_pending(run_id)
            text = str(event.get("content") or "")
            sidecars = [
                item
                for item in event.get("background_returns", [])
                if isinstance(item, Mapping)
            ]
            if text or sidecars:
                key = (run_id, group_id)
                current = rounds.setdefault(key, _Round())
                identity = str(
                    event.get("_id")
                    or event.get("sequence_num")
                    or event.get("message_id")
                    or ""
                )
                if not identity or identity not in current.seen:
                    current.chunks.append(text)
                    current.seen.add(identity)
                    current.event = event
                    for item in sidecars:
                        if item not in current.background_returns:
                            current.background_returns.append(item)
            # Reasoning is process information and may be shown before body admission.
            if event.get("reasoning_content"):
                await forward({**event, "content": "", "background_returns": []})
            return
        if name == "tool_start":
            tool_activity.add(run_id)
        if name == "model_round_end":
            current = rounds.pop((run_id, group_id), None)
            had_tool_activity = run_id in tool_activity
            tool_activity.discard(run_id)
            if not event.get("completed") or current is None:
                return
            if group_id in completed.setdefault(run_id, set()):
                return
            completed[run_id].add(group_id)
            text = "".join(current.chunks)
            if not text:
                if current.background_returns:
                    await forward(
                        {
                            **current.event,
                            "content": "",
                            "background_returns": current.background_returns,
                        }
                    )
                return
            context.delivery_candidate_seen = True
            source = current.event
            candidate = ReplyCandidate(
                run_id=run_id,
                session_id=context.kernel_session_id,
                turn_id=str(event.get("turn_id") or source.get("turn_id") or ""),
                group_id=group_id,
                candidate_id=group_id or str(source.get("message_id") or ""),
                text=text,
                metadata={
                    "run_origin": source.get("origin"),
                    "source_background_returns": current.background_returns,
                },
            )
            if source.get("event") == "gateway_message":
                await publish(candidate)
                return
            if had_tool_activity:
                await publish(candidate)
                return
            previous = pending.get(run_id)
            if previous is not None:
                await publish(previous)
            pending[run_id] = candidate
            return
        if name in {"turn_end", "run_terminal_reconcile", "run_reset_discard"} or (
            name == "run_status"
            and event.get("status") in {"completed", "failed", "cancelled"}
        ):
            successful_terminal = (
                name == "turn_end" and event.get("completed") is not False
            ) or (name == "run_status" and event.get("status") == "completed")
            if successful_terminal:
                await publish_pending(run_id, terminal_event=event)
            else:
                pending.pop(run_id, None)
            for key in tuple(rounds):
                if key[0] == run_id:
                    rounds.pop(key, None)
            completed.pop(run_id, None)
            tool_activity.discard(run_id)
            if name == "turn_end" and context.delivery_failed:
                await forward(
                    {
                        **event,
                        "event": "run_terminal_reconcile",
                        "reason": "delivery_withheld",
                        "finalize_bubble": True,
                        "delivery_status": "completed"
                        if context.visible_reply_committed
                        else "failed",
                    }
                )
                return
        await forward(event)

    return observe
