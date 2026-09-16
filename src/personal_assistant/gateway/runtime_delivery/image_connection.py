"""Project reply resources at the existing IM streaming-frame boundary."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from collections.abc import Callable, Mapping
from typing import Any

from personal_assistant.gateway.reply_image_stream import ReplyImageStream
from personal_assistant.gateway.reply_images import (
    ReplyImageContext,
    ReplyImages,
)
from .context import RunDeliveryContext, RunDeliveryContextStore
from .task_tracker import RuntimeDeliveryTaskTracker


@dataclass
class _Bubble:
    context: ReplyImageContext
    raw: str = ""
    stream: ReplyImageStream = field(default_factory=ReplyImageStream)
    projected: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ImageReplyConnection:
    """Keep image projection and public admission consistent across IM frame exits.

    This is a delivery-scoped view of the existing connection, not a second
    transport. Runtime events keep their raw model content; only outgoing frames
    use pending placeholders and completed private-resource URLs.
    """

    def __init__(
        self,
        connection: Any,
        *,
        reply_images: ReplyImages,
        context_store: RunDeliveryContextStore,
        task_tracker: RuntimeDeliveryTaskTracker,
        image_context_factory: Callable[[RunDeliveryContext, str], ReplyImageContext],
    ) -> None:
        self._connection = connection
        self._images = reply_images
        self._contexts = context_store
        self._tracker = task_tracker
        self._context_factory = image_context_factory
        self._bubbles: dict[tuple[str, str], _Bubble] = {}
        self._prepared: dict[str, tuple[str, str]] = {}

    def prepare_candidate(
        self, run_id: str, candidate_id: str, output_key: str, text: str
    ) -> None:
        """Register the immutable projection for one admitted complete candidate."""
        self._prepared[f"{run_id}:assistant_message:{candidate_id}"] = (
            output_key,
            text,
        )

    @property
    def connected(self) -> bool:
        """Return the underlying transport's current connection state."""
        return self._connection.connected

    def finish_external_shadow_run(self, run_id: str) -> None:
        """Preserve the underlying connection's shadow streaming lifecycle."""
        self._connection.finish_external_shadow_run(run_id)

    async def send_json(self, message_type: str, payload: Mapping[str, Any]) -> None:
        """Project an existing fire-and-forget runtime frame before sending."""
        await self._send("send_json", message_type, payload)

    async def send_json_await_ack(
        self, message_type: str, payload: Mapping[str, Any]
    ) -> Any:
        """Project an existing acknowledged runtime frame before sending."""
        return await self._send("send_json_await_ack", message_type, payload)

    async def _send(
        self, method: str, message_type: str, payload: Mapping[str, Any]
    ) -> Any:
        sender = getattr(self._connection, method)
        if message_type != "node.streaming_delta":
            return await sender(message_type, payload)
        run_id = str(payload.get("run_id") or "")
        kind = payload.get("kind")
        key = (run_id, str(payload.get("message_id") or ""))
        if kind == "message_discarded" and payload.get("reason") == "new_session":
            # Reset has already revoked this context. Its cleanup must not queue
            # behind an image upload which itself is waiting for reset's decision.
            self._bubbles.pop(key, None)
            return await sender(message_type, payload)
        context = self._contexts.get(run_id)
        if context is None:
            return None
        outgoing = dict(payload)
        bubble = self._bubbles.get(key)
        if kind in {"message_delta", "message_completed"}:
            if bubble is None:
                bubble = _Bubble(
                    self._context_factory(context, context.reply_output_key)
                )
                self._bubbles[key] = bubble
            async with bubble.lock:
                if kind == "message_delta":
                    text = str(payload.get("delta_text") or "")
                    prepared = self._prepared.get(
                        str(payload.get("idempotency_key") or "")
                    )
                    if prepared is not None:
                        output_key, projected = prepared
                        bubble.raw = projected
                        bubble.projected = True
                        outgoing["delta_text"] = projected
                        sender = self._connection.send_json_await_ack
                        self._images.record_delivery(
                            output_key,
                            "im",
                            {
                                "state": "pending",
                                "recovery": {
                                    "kind": "native_delta",
                                    "message_type": message_type,
                                    "payload": outgoing,
                                    "completion_payload": {
                                        "kind": "message_completed",
                                        "message_id": key[1],
                                        "run_id": run_id,
                                        "final_content": projected,
                                        "delivery_status": "completed",
                                    },
                                },
                            },
                        )
                        result = await self._publish(
                            sender, message_type, outgoing, run_id
                        )
                        if result is None:
                            raise ConnectionError(
                                "Image message receipt was not confirmed"
                            )
                        self._images.record_delivery(
                            output_key,
                            "im",
                            {
                                "state": "delivered",
                                "message_id": key[1],
                                "conversation_id": context.conversation_id,
                            },
                        )
                        self._prepared.pop(
                            str(payload.get("idempotency_key") or ""), None
                        )
                        return result
                    bubble.raw += text
                    outgoing["delta_text"] = bubble.stream.feed(text)
                    if not outgoing["delta_text"]:
                        return None
                else:
                    raw = payload.get("final_content")
                    if bubble.projected:
                        outgoing["final_content"] = bubble.raw
                    else:
                        if not isinstance(raw, str):
                            raw = bubble.raw or context.external_current_text
                        if raw:
                            prepared_reply = await asyncio.to_thread(
                                self._images.prepare, bubble.context, raw
                            )
                            outgoing["final_content"] = await self._images.project_im(
                                prepared_reply,
                                context.conversation_id,
                                agent_id=context.agent_id,
                            )
                    self._bubbles.pop(key, None)
                return await self._publish(sender, message_type, outgoing, run_id)
        if kind == "message_discarded":
            self._bubbles.pop(key, None)
        return await self._publish(sender, message_type, outgoing, run_id)

    async def _publish(
        self,
        sender: Callable[..., Any],
        message_type: str,
        payload: Mapping[str, Any],
        run_id: str,
    ) -> Any:
        if not await self._contexts.await_visibility(run_id):
            return None
        if not self._tracker.admit_publication(run_id):
            return None
        try:
            return await sender(message_type, payload)
        finally:
            self._tracker.release_publication(run_id)
