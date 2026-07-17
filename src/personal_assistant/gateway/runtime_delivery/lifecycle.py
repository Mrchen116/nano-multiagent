"""Own Gateway relay lifecycle delivery side effects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_models import RelayLifecycleUpdate
from personal_assistant.gateway.reply_visibility import is_protocol_silence_token
from personal_assistant.gateway.runtime_protocol import runtime_protocol_or_derive
from personal_assistant.reporter.upstream_reporter import UpstreamReporter
from personal_assistant.ws.im_connection import IMConnectionManager

from .context import RunDeliveryContextStore


def build_relay_lifecycle_callback(
    *,
    reporter: UpstreamReporter | None,
    im_connection_manager_factory: Callable[[], IMConnectionManager | None],
    run_context_store: dict[str, dict[str, str]]
    | RunDeliveryContextStore
    | None = None,
    owner_user_id: str = "",
    channel_registry: ChannelRegistry | None = None,
):
    """Build the relay lifecycle callback used by the inbound pipeline."""

    async def _callback(message: InboundMessage, update: RelayLifecycleUpdate) -> None:
        if update.phase == "accepted":
            _ack_external_message_processing_started(
                message,
                channel_registry=channel_registry,
            )
            _seed_run_context(
                message=message,
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
        protocol = runtime_protocol_or_derive(message)
        relay_task_id = protocol.relay_task_id
        if relay_task_id is None:
            return
        manager = im_connection_manager_factory()
        if manager is None:
            return
        if update.phase == "accepted":
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay_task_id,
                delivery_status="sent",
                detail=f"run_id={update.run_id}" if update.run_id is not None else None,
            )
            await manager.send_json("node.delivery_receipt", payload)
            return
        if update.phase == "running":
            message_id = protocol.im_message_id
            if message_id is None or update.run_id is None:
                return
            conversation_id = _protocol_conversation_id(message)
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
            message_id = protocol.im_message_id
            send_report = getattr(reporter, "send_report", None)
            if (
                callable(send_report)
                and message_id is not None
                and update.run_id is not None
            ):
                conversation_id = _protocol_conversation_id(message)
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
                relay_task_id=relay_task_id,
                delivery_status="completed",
                detail=receipt_detail,
            )
            await manager.send_json("node.delivery_receipt", payload)
            return
        if update.phase == "failed":
            message_id = protocol.im_message_id
            send_report = getattr(reporter, "send_report", None)
            if (
                callable(send_report)
                and message_id is not None
                and update.run_id is not None
            ):
                conversation_id = _protocol_conversation_id(message)
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
                relay_task_id=relay_task_id,
                delivery_status="failed",
                detail=update.error,
            )
            await manager.send_json("node.delivery_receipt", payload)

    return _callback


def _seed_run_context(
    *,
    message: InboundMessage,
    update: RelayLifecycleUpdate,
    run_context_store: dict[str, dict[str, str]] | RunDeliveryContextStore | None,
    owner_user_id: str,
) -> None:
    if run_context_store is None or not update.run_id:
        return
    if isinstance(run_context_store, RunDeliveryContextStore):
        run_context_store.seed_from_lifecycle(
            message=message,
            update=update,
            owner_user_id=owner_user_id,
        )
        return
    if update.run_id in run_context_store:
        return
    protocol = runtime_protocol_or_derive(message)
    shadow_ref = protocol.shadow_ref
    trigger_source = protocol.trigger_source or ""
    external_identity = protocol.external_identity
    relay_task_id = protocol.relay_task_id
    if shadow_ref is not None:
        conversation_id = shadow_ref.conversation_id
        to_user_id = ""
    elif relay_task_id is not None:
        conversation_id = message.external_chat_id
        to_user_id = ""
    elif external_identity is not None:
        conversation_id = ""
        to_user_id = ""
    else:
        conversation_id = ""
        to_user_id = owner_user_id
    agent_id_meta = (
        (external_identity.agent_id if external_identity else None)
        or update.agent_id
        or ""
    )
    run_context_store[update.run_id] = {
        "conversation_id": conversation_id,
        "message_id": "",
        "agent_id": agent_id_meta,
        "kernel_session_id": update.kernel_session_id or "",
        "to_user_id": to_user_id,
    }
    if trigger_source:
        run_context_store[update.run_id]["trigger_source"] = trigger_source
    if trigger_source and trigger_source != "im":
        channel_name = str(getattr(message, "channel_name", "") or "")
        run_context_store[update.run_id]["reply_channel_name"] = channel_name
        run_context_store[update.run_id]["reply_target_chat_id"] = (
            message.external_chat_id
        )
        thread_id = getattr(message, "thread_id", None)
        if thread_id:
            run_context_store[update.run_id]["reply_thread_id"] = str(thread_id)
        feishu_message_id = _metadata_text(message.metadata, key="feishu_message_id")
        if feishu_message_id is not None:
            run_context_store[update.run_id]["feishu_message_id"] = feishu_message_id


def _discard_run_context(
    *,
    run_context_store: dict[str, dict[str, str]] | RunDeliveryContextStore | None,
    run_id: str | None,
) -> None:
    if run_context_store is None or not run_id:
        return
    if isinstance(run_context_store, RunDeliveryContextStore):
        run_context_store.discard(run_id)
    else:
        run_context_store.pop(run_id, None)


def _protocol_conversation_id(message: InboundMessage) -> str:
    protocol = runtime_protocol_or_derive(message)
    if protocol.shadow_ref is not None:
        return protocol.shadow_ref.conversation_id
    return message.external_chat_id


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
