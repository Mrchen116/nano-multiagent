"""Own Gateway relay lifecycle delivery side effects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_models import (
    RelayLifecycleUpdate,
    RoutedInbound,
)
from personal_assistant.gateway.reply_visibility import is_protocol_silence_token
from personal_assistant.reporter.upstream_reporter import UpstreamReporter
from personal_assistant.ws.im_connection import IMConnectionManager

from .context import RunDeliveryContextStore


def build_relay_lifecycle_callback(
    *,
    reporter: UpstreamReporter | None,
    im_connection_manager_factory: Callable[[], IMConnectionManager | None],
    run_context_store: RunDeliveryContextStore | None = None,
    owner_user_id: str = "",
    channel_registry: ChannelRegistry | None = None,
):
    """Build the relay lifecycle callback used by the inbound pipeline."""

    async def _callback(routed: RoutedInbound, update: RelayLifecycleUpdate) -> None:
        message = routed.message
        if update.phase == "accepted":
            _ack_external_message_processing_started(
                message,
                channel_registry=channel_registry,
            )
            _seed_run_context(
                routed=routed,
                update=update,
                run_context_store=run_context_store,
                owner_user_id=owner_user_id,
            )
        elif update.phase == "recovery_adopted":
            _seed_run_context(
                routed=routed,
                update=update,
                run_context_store=run_context_store,
                owner_user_id=owner_user_id,
            )
        elif update.phase in ("completed", "failed", "cancelled"):
            _discard_run_context(
                run_context_store=run_context_store,
                run_id=update.run_id,
            )

        if reporter is None:
            return
        relay = message.ingress.im_relay
        if relay is None:
            return
        manager = im_connection_manager_factory()
        if manager is None:
            return
        if update.phase == "accepted":
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay.relay_task_id,
                delivery_status="sent",
                detail=f"run_id={update.run_id}" if update.run_id is not None else None,
            )
            await manager.send_json("node.delivery_receipt", payload)
            return
        if update.phase == "running":
            message_id = relay.im_message_id
            if message_id is None or update.run_id is None:
                return
            conversation_id = _protocol_conversation_id(routed)
            payload = reporter.send_report(
                run_id=update.run_id,
                status="running",
                agent_id=update.agent_id,
                session_key=update.session_key,
                conversation_id=conversation_id,
                message_id=message_id,
                summary=update.reply_text,
            )
            await manager.send_json("node.report", payload)
            return
        if update.phase == "completed":
            message_id = relay.im_message_id
            send_report = getattr(reporter, "send_report", None)
            if (
                callable(send_report)
                and message_id is not None
                and update.run_id is not None
            ):
                conversation_id = _protocol_conversation_id(routed)
                payload = send_report(
                    run_id=update.run_id,
                    status="completed",
                    agent_id=update.agent_id,
                    session_key=update.session_key,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    summary=update.reply_text,
                    detail=update.detail,
                    usage=update.usage,
                )
                await manager.send_json("node.report", payload)
            receipt_detail = _completed_receipt_detail(
                reply_text=update.reply_text,
                detail=update.detail,
            )
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay.relay_task_id,
                delivery_status="completed",
                detail=receipt_detail,
            )
            await manager.send_json("node.delivery_receipt", payload)
            return
        if update.phase == "failed":
            message_id = relay.im_message_id
            send_report = getattr(reporter, "send_report", None)
            if (
                callable(send_report)
                and message_id is not None
                and update.run_id is not None
            ):
                conversation_id = _protocol_conversation_id(routed)
                payload = send_report(
                    run_id=update.run_id,
                    status="failed",
                    agent_id=update.agent_id,
                    session_key=update.session_key,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    summary=update.error,
                )
                await manager.send_json("node.report", payload)
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay.relay_task_id,
                delivery_status="failed",
                detail=update.error,
            )
            await manager.send_json("node.delivery_receipt", payload)

    return _callback


def _seed_run_context(
    *,
    routed: RoutedInbound,
    update: RelayLifecycleUpdate,
    run_context_store: RunDeliveryContextStore | None,
    owner_user_id: str,
) -> None:
    if run_context_store is None or not update.run_id:
        return
    run_context_store.seed_from_lifecycle(
        routed=routed,
        update=update,
        owner_user_id=owner_user_id,
    )


def _discard_run_context(
    *,
    run_context_store: RunDeliveryContextStore | None,
    run_id: str | None,
) -> None:
    if run_context_store is None or not run_id:
        return
    run_context_store.discard(run_id)


def _protocol_conversation_id(routed: RoutedInbound) -> str:
    if routed.shadow.ref is not None:
        return routed.shadow.ref.conversation_id
    return routed.message.external_chat_id


def _ack_external_message_processing_started(
    message: InboundMessage, *, channel_registry: ChannelRegistry | None
) -> None:
    if channel_registry is None:
        return
    message_id = _metadata_text(message.metadata, key="feishu_message_id")
    if message_id is None:
        return
    channel = channel_registry.get(message.channel_name)
    if channel is None:
        return
    ack_message = getattr(channel, "ack_message", None)
    if not callable(ack_message):
        return
    ack_message(message_id)


def _completed_receipt_detail(
    *, reply_text: str | None, detail: Mapping[str, Any] | None
) -> str | None:
    suppression_detail = _suppression_detail(detail)
    if suppression_detail is None:
        return reply_text
    if is_protocol_silence_token(reply_text or ""):
        return suppression_detail
    return " | ".join(part for part in [reply_text, suppression_detail] if part) or None


def _suppression_detail(detail: Mapping[str, Any] | None) -> str | None:
    if detail is None:
        return None
    detail_parts = [f"{key}={value}" for key, value in detail.items()]
    return " | ".join(detail_parts) if detail_parts else None


def _metadata_text(metadata: Mapping[str, object], *, key: str) -> str | None:
    value = metadata.get(key)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
