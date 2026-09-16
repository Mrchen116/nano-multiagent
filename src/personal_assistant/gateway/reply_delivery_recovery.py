"""Replay unresolved image publications from saved destinations and provider receipts."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from personal_assistant.channels.base import (
    OutboundMessage,
    ProviderImageEntry,
    ProviderImagePreparation,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.reply_images import ReplyImages, external_retry_allowed


def external_recovery_payload(
    outbound: OutboundMessage, preparation: ProviderImagePreparation
) -> dict[str, Any]:
    """Freeze provider publication inputs without retaining original source paths."""
    return {
        "kind": "external_prepared",
        "outbound": {
            "channel_name": outbound.channel_name,
            "text": outbound.text,
            "target_chat_id": outbound.target_chat_id,
            "thread_id": outbound.thread_id,
            "metadata": dict(outbound.metadata),
        },
        "preparation": asdict(preparation),
    }


class ReplyDeliveryRecovery:
    """Drain bounded unresolved publications on the existing connection recovery hook."""

    def __init__(
        self,
        *,
        images: ReplyImages,
        im_connection_manager: Any,
        outbound_router: OutboundRouter,
        is_run_active: Callable[[str], bool] | None = None,
    ) -> None:
        self._images = images
        self._manager = im_connection_manager
        self._router = outbound_router
        self._is_run_active = is_run_active
        self._lock = asyncio.Lock()

    async def recover(self, *, limit: int = 100) -> int:
        """Retry saved identities once and retain unknown state for the next recovery.

        Args:
            limit: Maximum number of unresolved channel publications per pass.

        Returns:
            Number of publications newly confirmed; failures stay durable.
        """
        async with self._lock:
            return await self._recover(limit=limit)

    async def _recover(self, *, limit: int) -> int:
        delivered = 0
        for output_key, channel, receipt in self._images.unresolved_deliveries(
            limit=limit
        ):
            latest = self._images.delivery_receipt(output_key, channel)
            if (
                latest is None
                or latest.get("state", latest.get("status")) == "delivered"
            ):
                continue
            recovery = latest.get("recovery")
            if not isinstance(recovery, dict):
                continue
            try:
                kind = recovery["kind"]
                if kind == "explicit_message":
                    ack = await self._manager.send_agent_message(recovery["payload"])
                    confirmed = {"ack": ack.as_dict(), "message_id": ack.message_id}
                elif kind == "native_delta":
                    ack = await self._manager.send_json_await_ack(
                        recovery.get("message_type", "node.streaming_delta"),
                        recovery["payload"],
                    )
                    if ack is None:
                        continue
                    completion = recovery.get("completion_payload")
                    run_id = str(recovery["payload"].get("run_id") or "")
                    if completion is not None and not (
                        self._is_run_active and self._is_run_active(run_id)
                    ):
                        result = await self._manager.send_json_await_ack(
                            "node.streaming_delta", completion
                        )
                        if result is None:
                            continue
                    confirmed = {
                        "message_id": recovery["payload"].get("message_id"),
                        "conversation_id": recovery["payload"].get("conversation_id"),
                    }
                elif kind == "external_prepared":
                    if not external_retry_allowed(latest):
                        continue
                    outbound = OutboundMessage(**recovery["outbound"])
                    saved = recovery["preparation"]
                    preparation = ProviderImagePreparation(
                        connector_account_id=saved["connector_account_id"],
                        app_id=saved["app_id"],
                        entries=tuple(
                            ProviderImageEntry(**entry) for entry in saved["entries"]
                        ),
                    )
                    result = await self._router.send_prepared_async(
                        outbound,
                        preparation,
                        before_publish=lambda: external_retry_allowed(latest),
                    )
                    if result != "delivered":
                        continue
                    confirmed = {"message_id": getattr(result, "message_id", None)}
                else:
                    continue
                self._images.record_delivery(
                    output_key,
                    channel,
                    {
                        **latest,
                        **confirmed,
                        "state": "delivered",
                        "status": "delivered",
                    },
                )
                delivered += 1
            except Exception:
                # ACK loss is uncertain. Keep the exact original identity for replay.
                continue
        return delivered
