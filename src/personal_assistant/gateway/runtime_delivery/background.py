"""Deliver background/control replies and session notifications."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
import logging
from typing import Any

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.ws.im_connection import IMConnectionManager

_log = logging.getLogger("personal_assistant.gateway.runtime_delivery.background")


def _metadata_text(metadata: Mapping[str, Any], *, key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def build_session_event_callback(
    *,
    im_connection_manager_factory: Callable[[], "IMConnectionManager | None"],
    session_store: "SessionBindingStore",
) -> Callable[[str, Mapping[str, Any]], Awaitable[None]]:
    """Build a session event callback that sends self_evolution_review as IM system messages.

    When the background hook publishes ``self_evolution_review`` after a turn, this
    callback is invoked with the kernel_session_id and the raw event payload.  It
    resolves the conversation_id via the session binding store and sends a
    ``node.system_message`` frame to IM so users see a non-first-person notification.

    Args:
        im_connection_manager_factory: Returns the live IM connection manager (may be None).
        session_store: Gateway session binding store used to reverse-resolve conversation_id.

    Returns:
        Async callable ``(kernel_session_id, event) -> None``.
    """

    async def _callback(kernel_session_id: str, event: Mapping[str, Any]) -> None:
        manager = im_connection_manager_factory()
        if manager is None or not manager.connected:
            return

        event_name = event.get("event")
        if event_name != "self_evolution_review":
            return

        # Resolve conversation_id from the session binding.
        binding = session_store.find_by_kernel_session_id(kernel_session_id)
        if binding is None:
            return
        conversation_id = reply_context_im_conversation_id(binding.reply_context)
        if not conversation_id:
            return

        # Format a human-readable system notification matching the CLI style.
        # The SSE event dict is flat: the hook's payload fields (reviewed_skills,
        # reviewed_memory) are merged to the top level by the kernel stream, not
        # nested under "data".  Reading event["data"] here always missed them and
        # degraded every notification to the generic "self-evolution" subject.
        reviewed_skills: bool = bool(event.get("reviewed_skills", False))
        reviewed_memory: bool = bool(event.get("reviewed_memory", False))
        if reviewed_skills and reviewed_memory:
            subject = "skills + memory"
        elif reviewed_skills:
            subject = "skills"
        elif reviewed_memory:
            subject = "memory"
        else:
            subject = "self-evolution"
        text = f"· background self-evolution review: {subject} updated"

        try:
            await manager.send_json(
                "node.system_message",
                {
                    "conversation_id": conversation_id,
                    "text": text,
                },
            )
        except Exception as exc:  # noqa: BLE001
            # Background notification delivery must never crash the gateway.
            _log.warning(
                "session event notification delivery failed (conversation_id=%s): %s",
                conversation_id,
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
                result = external_reply_sender(cleaned_text, external_metadata)
                if asyncio.iscoroutine(result):
                    await result
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
