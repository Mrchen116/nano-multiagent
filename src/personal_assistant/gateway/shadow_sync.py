"""Mirror external-channel inbound messages into IM shadow conversations."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
import logging
from typing import Any

import httpx

from personal_assistant.channels.base import (
    ExternalInboundEventIdentity,
    InboundMessage,
)
from personal_assistant.gateway.im_http_transport import (
    build_im_http_headers,
    normalize_im_http_base_url,
)
from personal_assistant.gateway.runtime_protocol import (
    ExternalConversationIdentity,
    RuntimeProtocolFacts,
    ShadowConversationRef,
    attach_runtime_protocol,
    external_identity_from_message,
    strip_runtime_protocol_metadata,
)
from personal_assistant.gateway.shadow_saga import (
    ExternalShadowBubble,
    ExternalShadowBubbleEvent,
    ExternalShadowOutput,
    ExternalShadowSaga,
    ExternalShadowSagaStore,
)


def _metadata_text(metadata: Mapping[str, Any], *, key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


class ShadowSyncPendingError(RuntimeError):
    """Report a durable saga whose IM anchor remains unavailable."""

    def __init__(self, *, saga_id: str, cause: Exception) -> None:
        super().__init__(str(cause))
        self.saga_id = saga_id


class IMShadowConversationSync:
    """Mirror external-channel messages into recoverable IM shadow conversations."""

    def __init__(
        self,
        *,
        base_url: str,
        token_getter: Callable[[], Awaitable[str | None]],
        owner_user_id: str,
        timeout_seconds: float = 3.0,
        transport: httpx.AsyncBaseTransport | None = None,
        saga_store: ExternalShadowSagaStore | None = None,
        promote_pending_boundary: (
            Callable[[str, ShadowConversationRef], object] | None
        ) = None,
    ) -> None:
        self._base_url = normalize_im_http_base_url(base_url)
        self._token_getter = token_getter
        self._owner_user_id = owner_user_id.strip()
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._saga_store = saga_store
        self._promote_pending_boundary = promote_pending_boundary
        self._resolved_owner_user_id: str | None = None

    async def sync_user_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> ShadowConversationRef | None:
        identity = external_identity_from_message(message)
        if identity is None:
            if self._saga_store is not None:
                self._saga_store.prepare(
                    message=message,
                    agent_id=agent_id,
                    owner_id=self._owner_user_id,
                )
            return None
        if identity.trigger_source == "im":
            return None
        if message.external_event_identity is None:
            if self._saga_store is not None:
                self._saga_store.prepare(
                    message=message,
                    agent_id=agent_id,
                    owner_id=self._owner_user_id,
                )
            return None
        metadata = strip_runtime_protocol_metadata(message.metadata)
        external_source = identity.external_source
        external_chat_id = identity.external_chat_id
        token = await self._token_getter()
        headers = build_im_http_headers(token)
        saga_store = self._saga_store
        # The configured node owner is sufficient to identify the durable source fact.
        # Persist it before any IM request so an unavailable /me endpoint cannot erase an
        # external event that must later recover its user anchor and divider.
        saga = (
            saga_store.prepare(
                message=message,
                agent_id=agent_id,
                owner_id=self._owner_user_id,
            )
            if saga_store is not None and self._owner_user_id
            else None
        )
        if saga is not None and saga.shadow_ref is not None:
            self._promote_boundary(saga_id=saga.saga_id, shadow_ref=saga.shadow_ref)
            return saga.shadow_ref
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=self._timeout_seconds,
                trust_env=False,
                transport=self._transport,
            ) as client:
                owner_user_id = await self._resolve_owner_user_id(client)
                if (
                    saga is None
                    and saga_store is not None
                    and message.external_event_identity is not None
                ):
                    saga = saga_store.prepare(
                        message=message,
                        agent_id=agent_id,
                        owner_id=owner_user_id,
                    )
                elif saga is not None and saga.owner_id != owner_user_id:
                    raise ValueError(
                        "configured node owner differs from authenticated IM owner"
                    )
                conversation_response = await client.post(
                    "/im/v1/conversations/external/find-or-create",
                    json={
                        "external_source": external_source,
                        "external_chat_id": external_chat_id,
                        "agent_id": agent_id,
                        "title": _external_shadow_title(
                            metadata,
                            agent_id=agent_id,
                            external_source=external_source,
                            conversation_type=identity.conversation_type,
                        ),
                        "is_group": bool(message.is_group),
                        "participant_ids": [
                            f"user:{owner_user_id}",
                            f"agent:{agent_id}",
                        ],
                        "metadata": {
                            key: value
                            for key, value in metadata.items()
                            if isinstance(key, str)
                        },
                    },
                )
                conversation_response.raise_for_status()
                conversation_payload = conversation_response.json()
                conversation_id = str(conversation_payload.get("id") or "").strip()
                if not conversation_id:
                    raise ValueError("external shadow conversation response missing id")
                message_response = await client.post(
                    f"/im/v1/conversations/{conversation_id}/messages",
                    headers=_shadow_message_headers(
                        message,
                        saga_user_idempotency_key=(
                            saga.shadow_user_idempotency_key
                            if saga is not None
                            else None
                        ),
                    ),
                    json={
                        "sender_user_id": owner_user_id,
                        "sender_type": "user",
                        "content": message.text,
                        "sender_display_name": _metadata_text(
                            metadata, key="sender_display_name"
                        ),
                        "suppress_relay": True,
                    },
                )
                message_response.raise_for_status()
                message_payload = message_response.json()
                im_message_id = str(message_payload.get("id") or "").strip()
                if not im_message_id:
                    raise ValueError("external shadow message response missing id")
                shadow_ref = ShadowConversationRef(
                    conversation_id=conversation_id,
                    im_message_id=im_message_id,
                    shadow_saga_id=saga.saga_id if saga is not None else None,
                )
                if saga is not None:
                    saga_store = self._saga_store
                    assert saga_store is not None
                    saga_store.record_anchor(
                        saga_id=saga.saga_id, shadow_ref=shadow_ref
                    )
                    self._promote_boundary(saga_id=saga.saga_id, shadow_ref=shadow_ref)
                return shadow_ref
        except Exception as exc:
            if saga is None:
                raise
            raise ShadowSyncPendingError(saga_id=saga.saga_id, cause=exc) from exc

    def prepare_agent_output(
        self,
        *,
        saga_id: str,
        run_id: str,
        output_kind: str,
        kernel_message_id: str | None,
        content: str,
    ) -> ExternalShadowOutput:
        """Persist one Agent output before the external adapter receives it."""

        saga_store = self._saga_store
        if saga_store is None:
            raise RuntimeError("external shadow output requires durable saga storage")
        return saga_store.prepare_output(
            saga_id=saga_id,
            run_id=run_id,
            output_kind=output_kind,
            kernel_message_id=kernel_message_id,
            content=content,
        )

    def record_bubble_event(
        self, event: ExternalShadowBubbleEvent
    ) -> ExternalShadowBubble:
        """Persist one normalized external runtime fact before network delivery."""

        saga_store = self._saga_store
        if saga_store is None:
            raise RuntimeError("external shadow bubble requires durable saga storage")
        return saga_store.record(event)

    async def reconcile_snapshot(self, snapshot: ExternalShadowBubble) -> None:
        """Reconcile one terminal rich snapshot into its same-identity IM row."""

        saga_store = self._saga_store
        if saga_store is None:
            raise RuntimeError("external shadow bubble requires durable saga storage")
        saga = saga_store.require(snapshot.saga_id)
        shadow_ref = saga.shadow_ref
        if shadow_ref is None:
            return
        token = await self._token_getter()
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
            response = await client.put(
                f"/im/v1/conversations/{shadow_ref.conversation_id}/external-agent-messages/"
                f"{snapshot.shadow_message_id}",
                json={
                    "agent_id": saga.agent_id,
                    "content": snapshot.content,
                    "thinking": list(snapshot.thinking),
                    "tool_calls": list(snapshot.tool_calls),
                    "token_usage": token_payload,
                    "elapsed_ms": snapshot.elapsed_ms or 0,
                    "delivery_status": snapshot.delivery_status,
                    "kernel_message_id": snapshot.kernel_message_id,
                },
            )
            response.raise_for_status()
            message_id = str(response.json().get("id") or "").strip()
            if not message_id:
                raise ValueError("external shadow reconcile response missing id")
        saga_store.acknowledge(
            shadow_message_id=snapshot.shadow_message_id,
            im_message_id=message_id,
        )

    async def mirror_prepared_agent_output(self, output: ExternalShadowOutput) -> None:
        """Mirror an already durable Agent output without blocking external delivery.

        The event observer records the source fact synchronously before it permits the
        external provider write. This method receives that exact record so background
        IM mirroring cannot create a second local preparation step between those two
        delivery boundaries.
        """

        saga_store = self._saga_store
        if saga_store is None:
            raise RuntimeError("external shadow output requires durable saga storage")
        saga = saga_store.require(output.saga_id)
        if saga.shadow_ref is None:
            return
        await self._write_agent_output(saga=saga, output=output)

    async def mirror_agent_output(
        self,
        *,
        saga_id: str,
        run_id: str,
        output_kind: str,
        kernel_message_id: str | None,
        content: str,
    ) -> None:
        """Persist and mirror one Agent output without blocking external delivery.

        This convenience entry point owns both steps for direct callers. Runtime event
        delivery instead uses :meth:`mirror_prepared_agent_output` after it has made
        the source fact durable before calling the external provider.
        """

        output = self.prepare_agent_output(
            saga_id=saga_id,
            run_id=run_id,
            output_kind=output_kind,
            kernel_message_id=kernel_message_id,
            content=content,
        )
        await self.mirror_prepared_agent_output(output)

    async def _write_agent_output(
        self, *, saga: ExternalShadowSaga, output: ExternalShadowOutput
    ) -> None:
        shadow_ref = saga.shadow_ref
        if shadow_ref is None:
            raise ValueError("shadow output requires a confirmed user anchor")
        token = await self._token_getter()
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=build_im_http_headers(token),
            timeout=self._timeout_seconds,
            trust_env=False,
            transport=self._transport,
        ) as client:
            response = await client.post(
                f"/im/v1/conversations/{shadow_ref.conversation_id}/messages",
                headers={"Idempotency-Key": output.caller_idempotency_key},
                json={
                    "sender": {"type": "agent", "id": saga.agent_id},
                    "content": output.content,
                    "suppress_relay": True,
                },
            )
            response.raise_for_status()
            message_id = str(response.json().get("id") or "").strip()
            if not message_id:
                raise ValueError("external shadow agent message response missing id")
        saga_store = self._saga_store
        assert saga_store is not None
        saga_store.record_output_anchor(output=output, im_message_id=message_id)

    def _promote_boundary(
        self, *, saga_id: str, shadow_ref: ShadowConversationRef
    ) -> None:
        promoter = self._promote_pending_boundary
        if promoter is not None:
            promoter(saga_id, shadow_ref)

    def schedule_recovery(self) -> asyncio.Task[None] | None:
        """Schedule replay of user anchors left pending by a prior Gateway process."""

        if self._saga_store is None:
            return None
        task = asyncio.create_task(self.recover_pending())
        task.add_done_callback(self._report_recovery_failure)
        return task

    async def recover_pending(self) -> None:
        """Replay every pending shadow-user anchor using its persisted provider identity."""

        saga_store = self._saga_store
        if saga_store is None:
            return
        for saga in saga_store.pending():
            payload = json.loads(saga.canonical_inbound_json)
            external_event = payload["external_event_identity"]
            message = attach_runtime_protocol(
                InboundMessage(
                    channel_name=str(payload["channel_name"]),
                    text=str(payload["text"]),
                    external_user_id=str(payload["external_user_id"]),
                    external_chat_id=str(payload["external_chat_id"]),
                    is_group=bool(payload["is_group"]),
                    agent_id=saga.agent_id,
                    thread_id=payload.get("thread_id"),
                    metadata=payload["metadata"],
                    external_event_identity=ExternalInboundEventIdentity(
                        connector_account_id=str(
                            external_event["connector_account_id"]
                        ),
                        provider_event_id=str(external_event["provider_event_id"]),
                    ),
                ),
                RuntimeProtocolFacts(
                    external_identity=ExternalConversationIdentity(
                        external_source=str(
                            payload["external_identity"]["external_source"]
                        ),
                        external_chat_id=str(
                            payload["external_identity"]["external_chat_id"]
                        ),
                        agent_id=saga.agent_id,
                        conversation_type=payload["external_identity"].get(
                            "conversation_type"
                        ),
                        trigger_source=payload["external_identity"].get(
                            "trigger_source"
                        ),
                    )
                ),
            )
            await self.sync_user_message(message, agent_id=saga.agent_id)
        for snapshot in saga_store.pending_snapshots():
            saga = saga_store.require(snapshot.saga_id)
            if saga.shadow_ref is None:
                continue
            await self.reconcile_snapshot(snapshot)
        for output in saga_store.pending_outputs():
            saga = saga_store.require(output.saga_id)
            if saga.shadow_ref is None:
                continue
            await self._write_agent_output(saga=saga, output=output)

    @staticmethod
    def _report_recovery_failure(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception:
            logging.getLogger(__name__).exception("external shadow recovery failed")

    async def _resolve_owner_user_id(self, client: httpx.AsyncClient) -> str:
        if self._resolved_owner_user_id:
            return self._resolved_owner_user_id
        response = await client.get("/im/v1/me")
        response.raise_for_status()
        payload = response.json()
        user_id = payload.get("id") or payload.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("IM /me response missing user id")
        self._resolved_owner_user_id = user_id.strip()
        return self._resolved_owner_user_id


def _shadow_message_headers(
    message: InboundMessage, *, saga_user_idempotency_key: str | None
) -> dict[str, str] | None:
    """Return the stable caller key for one provider-owned shadow message."""

    if saga_user_idempotency_key is not None:
        return {"Idempotency-Key": saga_user_idempotency_key}
    event_identity = message.external_event_identity
    external_identity = external_identity_from_message(message)
    if event_identity is None or external_identity is None:
        return None
    return {
        "Idempotency-Key": (
            f"shadow-user:{external_identity.external_source}:"
            f"{event_identity.connector_account_id}:{event_identity.provider_event_id}"
        )
    }


def _external_shadow_title(
    metadata: Mapping[str, object],
    *,
    agent_id: str,
    external_source: str,
    conversation_type: str | None = None,
) -> str:
    title = _metadata_text(metadata, key="conversation_title")
    if title is not None:
        return title
    chat_name = _metadata_text(metadata, key="chat_name")
    conversation_type = conversation_type or _metadata_text(
        metadata, key="conversation_type"
    )
    if conversation_type == "group":
        return f"{agent_id} · {chat_name or '群聊'} · {external_source}"
    return f"{agent_id} · {external_source}"
