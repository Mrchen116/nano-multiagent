"""Publish projected shadow replies and acknowledge their durable IM identities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx

from personal_assistant.gateway.im_http_transport import (
    build_im_http_headers,
    normalize_im_http_base_url,
)
from personal_assistant.gateway.shadow_saga import (
    ExternalShadowBubble,
    ExternalShadowOutput,
    ExternalShadowSaga,
    ExternalShadowSagaStore,
)


class ShadowReplyPublisher:
    """Own shadow reply HTTP and saga receipts, independent of delivery policy.

    Args:
        base_url: IM service HTTP or WebSocket URL.
        gateway_token_getter: Current registered Gateway credential provider.
        saga_store: Same durable store used for inbound shadow preparation.
        timeout_seconds: Timeout for each IM request.
        transport: Optional HTTP transport for isolated protocol tests.
        before_publish: Existing runtime admission gate, called before a write.
        after_publish: Release hook for each admitted write, including failures.
    """

    def __init__(
        self,
        *,
        base_url: str,
        gateway_token_getter: Callable[[], Awaitable[str | None]],
        saga_store: ExternalShadowSagaStore,
        timeout_seconds: float = 3.0,
        transport: httpx.AsyncBaseTransport | None = None,
        before_publish: Callable[[str], Awaitable[bool]] | None = None,
        after_publish: Callable[[str], None] | None = None,
    ) -> None:
        self._base_url = normalize_im_http_base_url(base_url)
        self._gateway_token_getter = gateway_token_getter
        self._saga_store = saga_store
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._before_publish = before_publish
        self._after_publish = after_publish

    async def _require_gateway_token(self) -> str:
        token = await self._gateway_token_getter()
        if not token:
            raise ConnectionError(
                "IM shadow data requires a registered Gateway connection"
            )
        return token

    async def publish_output(
        self, saga: ExternalShadowSaga, output: ExternalShadowOutput, content: str
    ) -> str | None:
        """Publish projected content and durably acknowledge its output identity.

        Args:
            saga: Durable external conversation with a confirmed IM anchor.
            output: Prepared output carrying the stable caller idempotency key.
            content: Already projected reply body; this method does no image I/O.

        Returns:
            IM message id, or None when publication admission was revoked.
        """
        shadow_ref = saga.shadow_ref
        if shadow_ref is None:
            raise ValueError("shadow output requires a confirmed user anchor")
        token = await self._require_gateway_token()
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=build_im_http_headers(token),
            timeout=self._timeout_seconds,
            trust_env=False,
            transport=self._transport,
        ) as client:
            if self._before_publish is not None and not await self._before_publish(
                output.run_id
            ):
                self._saga_store.discard_output(output)
                return
            try:
                response = await client.post(
                    f"/im/v1/conversations/{shadow_ref.conversation_id}/messages",
                    params={"agent_id": saga.agent_id},
                    headers={"Idempotency-Key": output.caller_idempotency_key},
                    json={
                        "sender": {"type": "agent", "id": saga.agent_id},
                        "content": content,
                        "suppress_relay": True,
                    },
                )
                response.raise_for_status()
            finally:
                if self._after_publish is not None:
                    self._after_publish(output.run_id)
            message_id = str(response.json().get("id") or "").strip()
            if not message_id:
                raise ValueError("external shadow agent message response missing id")
        saga_store = self._saga_store
        saga_store.record_output_anchor(output=output, im_message_id=message_id)

        return message_id

    async def publish_snapshot(
        self, saga: ExternalShadowSaga, snapshot: ExternalShadowBubble, content: str
    ) -> str | None:
        """Reconcile projected rich content into its stable IM message row.

        Args:
            saga: Durable external conversation with a confirmed IM anchor.
            snapshot: Rich bubble state and stable shadow message identity.
            content: Already projected reply body.

        Returns:
            IM message id, or None when publication admission was revoked.
        """
        saga_store = self._saga_store
        shadow_ref = saga.shadow_ref
        if shadow_ref is None:
            raise ValueError("shadow snapshot requires a confirmed user anchor")
        token = await self._require_gateway_token()
        token_usage = snapshot.token_usage
        token_payload = None
        if token_usage is not None:
            prompt = int(token_usage.get("prompt") or 0)
            completion = int(token_usage.get("completion") or 0)
            token_payload = {
                "output": completion,
                "context_used": prompt,
                "context_window": int(token_usage.get("context_window") or 0),
                "total": int(token_usage.get("total") or prompt + completion),
                "cache_read_tokens": int(token_usage.get("cache_read") or 0),
                "cache_total_input_tokens": int(
                    token_usage.get("cache_total_input") or 0
                ),
            }
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=build_im_http_headers(token),
            timeout=self._timeout_seconds,
            trust_env=False,
            transport=self._transport,
        ) as client:
            if self._before_publish is not None and not await self._before_publish(
                snapshot.run_id
            ):
                saga_store.discard_snapshot(snapshot.shadow_message_id)
                return
            try:
                response = await client.put(
                    f"/im/v1/conversations/{shadow_ref.conversation_id}/external-agent-messages/"
                    f"{snapshot.shadow_message_id}",
                    params={"agent_id": saga.agent_id},
                    json={
                        "agent_id": saga.agent_id,
                        "content": content,
                        "thinking": list(snapshot.thinking),
                        "tool_calls": list(snapshot.tool_calls),
                        "token_usage": token_payload,
                        "elapsed_ms": snapshot.elapsed_ms or 0,
                        "delivery_status": snapshot.delivery_status,
                        "kernel_message_id": snapshot.kernel_message_id,
                    },
                )
                response.raise_for_status()
            finally:
                if self._after_publish is not None:
                    self._after_publish(snapshot.run_id)
            message_id = str(response.json().get("id") or "").strip()
            if not message_id:
                raise ValueError("external shadow reconcile response missing id")
        saga_store.acknowledge(
            shadow_message_id=snapshot.shadow_message_id,
            im_message_id=message_id,
        )

        return message_id
