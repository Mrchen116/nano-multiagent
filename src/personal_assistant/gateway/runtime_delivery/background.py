"""Deliver background/control replies and session notifications."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
import inspect
import logging
from typing import Any
from uuid import uuid4

from personal_assistant.channels.base import ReplyContext
from personal_assistant.ws.im_connection import IMConnectionManager

_log = logging.getLogger("personal_assistant.gateway.runtime_delivery.background")


def _metadata_text(metadata: Mapping[str, Any], *, key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


async def _invoke_external_reply_sender(
    sender: Callable[[str, Mapping[str, str]], Any],
    text: str,
    metadata: Mapping[str, str],
) -> None:
    """Call a channel sender without blocking the Gateway event loop.

    Composition supplies a synchronous OutboundRouter sender, while tests and
    alternate channel integrations may return an awaitable. Calling the sender in a
    worker thread preserves the synchronous path's retry behavior; awaiting a returned
    awaitable on this loop preserves the asynchronous contract.
    """
    result = await asyncio.to_thread(sender, text, metadata)
    if inspect.isawaitable(result):
        await result


def build_session_event_callback(
    *,
    im_connection_manager_factory: Callable[[], "IMConnectionManager | None"],
    external_reply_sender: Callable[[str, Mapping[str, str]], Any] | None = None,
    delivery_incarnation: str | None = None,
) -> Callable[[ReplyContext, str, str, Mapping[str, Any]], Awaitable[None]]:
    """Build delivery for truthful self-evolution update receipts.

    When the background hook publishes ``self_evolution_review`` after a turn, this
    callback is invoked with the kernel_session_id and the raw event payload.  It
    sends a ``node.system_message`` frame to shadow IM and, for an external trigger,
    a plain-text receipt through the existing outbound router.

    Args:
        im_connection_manager_factory: Returns the live IM connection manager (may be None).
        external_reply_sender: Existing ordinary-message sender used only when the
            event-specific reply context originated from an external channel.
        delivery_incarnation: Optional process-local identity used by deterministic tests.
    Returns:
        Async callable ``(reply_context, agent_id, kernel_session_id, event) -> None``.
    """

    incarnation = delivery_incarnation or uuid4().hex

    async def _callback(
        reply_context: ReplyContext,
        agent_id: str,
        kernel_session_id: str,
        event: Mapping[str, Any],
    ) -> None:
        event_name = event.get("event")
        if event_name != "self_evolution_review":
            return

        raw_targets = event.get("updated_targets")
        if not isinstance(raw_targets, (list, tuple)):
            return
        updated_targets = [
            target for target in ("skills", "memory") if target in raw_targets
        ]
        if not updated_targets:
            return
        conversation_id = reply_context_im_conversation_id(reply_context)
        raw_sequence = event.get("_id") or event.get("sequence_num")
        if (
            not isinstance(raw_sequence, int)
            or isinstance(raw_sequence, bool)
            or raw_sequence <= 0
        ):
            _log.warning(
                "session event notification skipped without sequence "
                "(conversation_id=%s agent_id=%s kernel_session_id=%s)",
                conversation_id,
                agent_id,
                kernel_session_id,
            )
            return
        identity = (
            f"self-evolution-review:{incarnation}:{kernel_session_id}:{raw_sequence}"
        )
        reviewed_skills = "skills" in updated_targets
        reviewed_memory = "memory" in updated_targets
        if reviewed_skills and reviewed_memory:
            subject = "skills + memory"
        elif reviewed_skills:
            subject = "skills"
        elif reviewed_memory:
            subject = "memory"
        text = f"· background self-evolution review: {subject} updated"

        external_metadata = reply_context_external_delivery_metadata(
            reply_context,
            from_session_id=identity,
        )
        if external_metadata is not None and external_reply_sender is not None:
            try:
                await _invoke_external_reply_sender(
                    external_reply_sender,
                    text,
                    external_metadata,
                )
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "self-evolution notice external delivery failed "
                    "(channel=%s target=%s kernel_session_id=%s sequence=%s): %s",
                    external_metadata.get("channel_name", ""),
                    external_metadata.get("target_chat_id", ""),
                    kernel_session_id,
                    raw_sequence,
                    exc,
                )

        if not conversation_id:
            return
        manager = im_connection_manager_factory()
        if manager is None:
            _log.warning(
                "session event notification has no IM connection manager "
                "(conversation_id=%s agent_id=%s kernel_session_id=%s sequence=%s)",
                conversation_id,
                agent_id,
                kernel_session_id,
                raw_sequence,
            )
            return
        if not manager.connected:
            _log.warning(
                "session event notification queued while IM is disconnected "
                "(conversation_id=%s agent_id=%s kernel_session_id=%s sequence=%s)",
                conversation_id,
                agent_id,
                kernel_session_id,
                raw_sequence,
            )
        try:
            ack = await manager.send_json_await_ack(
                "node.system_message",
                {
                    "conversation_id": conversation_id,
                    "idempotency_key": identity,
                    "text": text,
                    "system_notice": {
                        "kind": "self_evolution_review",
                        "source_agent_id": agent_id,
                        "updated_targets": updated_targets,
                    },
                },
            )
            message_id = ack.get("message_id")
            if not isinstance(message_id, str) or not message_id.strip():
                raise ValueError("node.system_message ACK missing message_id")
        except Exception as exc:  # noqa: BLE001
            # Background notification delivery must never crash the gateway.
            _log.warning(
                "session event notification delivery failed "
                "(conversation_id=%s agent_id=%s kernel_session_id=%s sequence=%s): %s",
                conversation_id,
                agent_id,
                kernel_session_id,
                raw_sequence,
                exc,
            )

    return _callback


def build_bg_reply_sender(
    *,
    im_connection_manager_factory: "Callable[[], IMConnectionManager | None]",
    external_reply_sender: Callable[[str, Mapping[str, str]], Any] | None = None,
) -> "Callable[[str, Any, str], Awaitable[None]]":
    """Build an async callable that relays user-visible agent/control text.

    Called by InboundPipeline's bg_run_output_callback when a BACKGROUND_TASK-origin
    run emits an assistant_message event, and by control paths such as /stop/image
    failure that are not normal kernel assistant bubbles. Feishu-triggered contexts are
    sent to the original external channel and shadow IM; IM-triggered contexts stay in
    IM.

    Args:
        im_connection_manager_factory: Returns the live IM connection manager (may be None).
        external_reply_sender: Optional sender for external-channel visible text.

    Returns:
        Async callable ``(text, reply_context, from_session_id) -> None``.
        ``from_session_id`` should carry the ``|tool_call:<key>`` suffix built
        by the caller (inbound_pipeline) for IM-side deduplication (bugfix-404 F1).
    """
    from personal_assistant.channels.base import ReplyContext as _RC  # noqa: PLC0415

    async def _sender(text: str, reply_context: _RC, from_session_id: str) -> None:
        cleaned_text = text.strip()
        if not from_session_id or not cleaned_text:
            return

        external_metadata = reply_context_external_delivery_metadata(
            reply_context,
            from_session_id=from_session_id,
        )
        if external_metadata is not None and external_reply_sender is not None:
            try:
                await _invoke_external_reply_sender(
                    external_reply_sender,
                    cleaned_text,
                    external_metadata,
                )
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "visible text external delivery failed (channel=%s target=%s): %s",
                    external_metadata.get("channel_name", ""),
                    external_metadata.get("target_chat_id", ""),
                    exc,
                )

        manager = im_connection_manager_factory()
        if manager is None or not manager.connected:
            return
        conversation_id = reply_context_im_conversation_id(reply_context)
        if not conversation_id:
            return
        try:
            await manager.send_agent_message(
                {
                    "text": cleaned_text,
                    "to": conversation_id,
                    # from_session_id carries optional "|tool_call:<key>" suffix so
                    # IM deduplicates replayed bg replies (bugfix-404 F1).
                    "from_session_id": from_session_id,
                }
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "bg_reply_sender send_agent_message failed (conv=%s from=%s): %s",
                conversation_id,
                from_session_id,
                exc,
            )

    return _sender


def reply_context_im_conversation_id(reply_context: ReplyContext) -> str | None:
    """Return the IM conversation id for a reply context, if one exists."""
    metadata = dict(reply_context.metadata)
    shadow_id = _metadata_text(metadata, key="shadow_conversation_id")
    if shadow_id is not None:
        return shadow_id
    conversation_id = _metadata_text(metadata, key="conversation_id")
    if conversation_id is not None:
        return conversation_id
    if reply_context.channel_name == "web_relay":
        target = reply_context.target_chat_id.strip()
        return target or None
    return None


def reply_context_external_delivery_metadata(
    reply_context: ReplyContext,
    *,
    from_session_id: str,
) -> dict[str, str] | None:
    """Build external-channel delivery metadata for user-visible control/bg text."""
    metadata = dict(reply_context.metadata)
    trigger_source = _metadata_text(metadata, key="trigger_source")
    external_source = _metadata_text(metadata, key="external_source")
    if (
        trigger_source == "im"
        or reply_context.channel_name == "web_relay"
        or not reply_context.target_chat_id.strip()
        or (trigger_source is None and external_source is None)
    ):
        return None
    delivery: dict[str, str] = {
        "channel_name": reply_context.channel_name,
        "target_chat_id": reply_context.target_chat_id,
        "reply_phase": visible_reply_phase_from_session_id(from_session_id),
        "reply_dedupe_key": from_session_id,
    }
    if reply_context.thread_id:
        delivery["reply_thread_id"] = reply_context.thread_id
    feishu_message_id = _metadata_text(metadata, key="feishu_message_id")
    if feishu_message_id is not None:
        delivery["feishu_message_id"] = feishu_message_id
    return delivery


def visible_reply_phase_from_session_id(from_session_id: str) -> str:
    """Classify non-kernel visible text for adapter lifecycle handling."""
    lowered = from_session_id.lower()
    if ":stop-" in lowered or ":image-error-" in lowered or ":permission-" in lowered:
        return "control"
    return "intermediate"
