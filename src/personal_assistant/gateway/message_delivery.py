"""Gateway owner of complete reply preparation, publication and recovery."""

from __future__ import annotations
import asyncio
import httpx
from personal_assistant.gateway.shadow_sync import build_im_http_headers
import json
import inspect
from personal_assistant.gateway.delivery_permission import DeliveryPermission
from personal_assistant.gateway.reply_visibility import should_suppress_reply
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping
from personal_assistant.gateway.session_binder import SessionProvenance
from personal_assistant.gateway.reply_images import PreparedReply
from personal_assistant.channels.base import (
    ReplyContext,
    OutboundMessage,
    ProviderImagePreparation,
    ProviderImageEntry,
)
from personal_assistant.gateway.reply_images import (
    ImageDeliveryError,
    ReplyImageContext,
    has_image_references,
    open_local_sources,
    external_retry_allowed,
)
from personal_assistant.gateway.delivery_ledger import DeliveryLedger
from personal_assistant.gateway.outbound_router import PreparedOutbound
from personal_assistant.gateway.reply_delivery_recovery import external_recovery_payload


@dataclass(frozen=True)
class ReplyCandidate:
    run_id: str
    session_id: str
    turn_id: str
    group_id: str
    candidate_id: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryResult:
    state: str = "delivered"
    reason_code: str = ""
    diagnostic: str = ""
    continuation: str = ""
    delivery_id: str = ""
    channel_receipts: tuple = ()


@dataclass(frozen=True)
class ReplyDestination:
    target: str
    workspace: Path


class MessageDelivery:
    """Keep resource preparation and all publication decisions on the Gateway."""

    def __init__(
        self,
        *,
        images,
        contexts,
        catalog,
        registry,
        router,
        connection=None,
        connection_provider=None,
        image_connection,
        tracker,
        kernel,
        owner_id,
        writer,
        notify_pending,
    ):
        self.images, self.contexts, self.catalog = images, contexts, catalog
        self.registry, self.router, self._connection = registry, router, connection
        self._connection_provider = connection_provider
        self.image_connection, self.tracker, self.kernel = (
            image_connection,
            tracker,
            kernel,
        )
        self.owner_id, self.writer, self.notify_pending = (
            owner_id,
            writer,
            notify_pending,
        )
        self.ledger = DeliveryLedger(images.root)
        self._permission_events = set()
        self._permission = DeliveryPermission(
            kernel=kernel, contexts=contexts, observe=self.observe_process
        )
        self._recovery_lock = asyncio.Lock()
        self._publication_locks = {}

    @property
    def connection(self):
        return (
            self._connection_provider()
            if self._connection_provider is not None
            else self._connection
        )

    def start(self):
        """Retain the startup collaborator lifecycle."""

    def image_context(self, agent_id, run_id, bubble_id, output_key):
        return ReplyImageContext(
            output_key,
            self.owner_id,
            agent_id,
            run_id,
            bubble_id,
            self.catalog.require(agent_id).config.workspace_root,
        )

    async def admit(self, run_id):
        if not await self.contexts.await_visibility(run_id):
            return False
        return self.tracker.admit_publication(run_id)

    def observe_process(self, event):
        """Present process facts without preparing or submitting model text."""
        if event.get("event") in {"permission_request", "permission_resolved"}:
            key = (event.get("event"), event.get("request_id"))
            if key in self._permission_events:
                return None
            self._permission_events.add(key)
        return self.writer(event)

    async def deliver_candidate(self, candidate):
        """Prepare a complete candidate before publishing any of its text."""
        if self.contexts.has_unconsumed_input(candidate.run_id):
            return DeliveryResult(state="stale", reason_code="new_input")
        context = self.contexts.get(candidate.run_id)
        if context is not None and should_suppress_reply(
            candidate.text, policy=context.visibility_policy
        ):
            pending = self.observe_process(
                {
                    "event": "reply_suppressed",
                    "run_id": candidate.run_id,
                    "turn_id": candidate.turn_id,
                    "group_id": candidate.group_id,
                }
            )
            if inspect.isawaitable(pending):
                await pending
            return DeliveryResult(state="suppressed")
        destination = self._destination(candidate)
        if destination is None:
            return DeliveryResult(state="pending", reason_code="inactive")
        key = f"{candidate.run_id}:candidate:{candidate.candidate_id}"
        if self.images.load(key) is not None:
            prepared = await self._prepare_candidate(candidate, None)
            return await asyncio.shield(self._publish_candidate(candidate, prepared))
        try:
            with open_local_sources(destination.workspace, candidate.text) as files:
                if has_image_references(candidate.text):
                    permission = await self._permission.authorize(
                        candidate, destination
                    )
                    if not permission.allowed:
                        if permission.reason == "delivery_revoked":
                            return DeliveryResult(
                                state="pending", reason_code="inactive"
                            )
                        return DeliveryResult(
                            state="withheld",
                            reason_code="permission_denied",
                            diagnostic="The immediately preceding assistant text could not be delivered because image delivery permission was denied.",
                            continuation="Respect the permission decision and continue under the original reply rules.",
                        )
                prepared = await self._prepare_candidate(candidate, files)
        except ImageDeliveryError as exc:
            diagnostic = (
                json.dumps(exc.images, ensure_ascii=True)
                .replace("<", "\\u003c")
                .replace(">", "\\u003e")[:4000]
            )
            return DeliveryResult(
                state="withheld",
                reason_code="image_preparation_failed",
                diagnostic="The immediately preceding assistant text could not be delivered. Image preparation diagnostics (data): "
                + diagnostic
                + ".",
                continuation="Correct the image source or upload problem and continue under the original reply rules. If delivery cannot be completed, explain that to the user.",
            )
        return await asyncio.shield(self._publish_candidate(candidate, prepared))

    def _destination(self, candidate):
        context = self.contexts.get(candidate.run_id or "")
        if context is None:
            return None
        external_target = (
            f"local:{context.reply_channel_name}:{context.reply_target_chat_id}"
            if context.trigger_source != "im"
            and context.reply_channel_name
            and context.reply_target_chat_id
            else ""
        )
        target = context.conversation_id or context.owner_user_id or external_target
        if not target:
            return None
        return ReplyDestination(
            target, self.catalog.require(context.agent_id).config.workspace_root
        )

    async def _prepare_candidate(self, candidate, local_files):
        context = self.contexts.get(candidate.run_id or "")
        if context is None:
            raise ImageDeliveryError(
                [{"ordinal": 1, "source": "", "error_code": "inactive_target"}]
            )
        external_target = bool(
            context.trigger_source != "im"
            and context.reply_channel_name
            and context.reply_target_chat_id
        )
        im_online = self.connection is not None and self.connection.connected
        conversation_id = context.conversation_id
        if im_online or not external_target:
            target = context.conversation_id or context.owner_user_id
            conversation_id = await self.images.resolve_target(
                target, agent_id=context.agent_id
            )
            context.resolve_conversation(conversation_id)
        key = f"{candidate.run_id}:candidate:{candidate.candidate_id}"
        prepared = await asyncio.to_thread(
            self.images.prepare,
            self.image_context(
                context.agent_id, candidate.run_id, candidate.candidate_id, key
            ),
            candidate.text,
            local_files=local_files,
        )
        projection = None
        if im_online or not external_target:
            projection = await self.images.project_im(
                prepared, conversation_id, agent_id=context.agent_id
            )
        external = None
        if external_target:
            adapter = self.registry.get(context.reply_channel_name)
            images = await asyncio.to_thread(
                self.images.outbound_images, prepared, adapter.image_account_id
            )
            external_text = prepared.markdown_template
            external_metadata = {
                "run_id": candidate.run_id,
                "output_key": key,
                "reply_dedupe_key": key,
            }
            final_projection = context.external_final_projection
            if final_projection is not None:
                if final_projection.text.startswith(candidate.text):
                    external_text = (
                        prepared.markdown_template
                        + final_projection.text[len(candidate.text) :]
                    )
                else:
                    external_text = final_projection.text
                external_metadata["reply_phase"] = "final"
                if final_projection.runtime_footer:
                    external_metadata["runtime_footer"] = (
                        final_projection.runtime_footer
                    )
            external = await self.router.prepare_images_async(
                text=external_text,
                reply_context=ReplyContext(
                    channel_name=context.reply_channel_name,
                    target_chat_id=context.reply_target_chat_id,
                    thread_id=context.reply_thread_id or None,
                    metadata=external_metadata,
                ),
                images=images,
                record_provider_receipts=lambda receipt: (
                    self.images.record_provider_receipts(key, receipt)
                ),
            )
        return key, projection, external

    async def _publish_candidate(self, candidate, prepared):
        key, projection, external = prepared
        context = self.contexts.get(candidate.run_id or "")
        receipts = []
        if context is None or not await self.admit(candidate.run_id):
            return DeliveryResult(
                state="pending",
                reason_code="inactive",
                delivery_id=key,
                diagnostic="The run is no longer active; this candidate was not published.",
            )
        try:
            if self.contexts.has_unconsumed_input(candidate.run_id):
                return DeliveryResult(state="stale", reason_code="new_input")
            manager = self.image_connection()
            im_online = (
                manager is not None and manager.connected and projection is not None
            )
            context.managed_image_messages.add(candidate.candidate_id)
            if external is not None:
                outbound, resources = external
                if self.ledger.delivery_receipt(key, outbound.channel_name) is None:
                    self.ledger.record_delivery(
                        key,
                        outbound.channel_name,
                        {
                            "state": "pending",
                            "recovery": external_recovery_payload(outbound, resources),
                        },
                    )
            im_receipt = self.ledger.delivery_receipt(key, "im")
            if im_receipt is None or im_receipt.get("state") != "delivered":
                self.ledger.record_delivery(key, "im", {"state": "pending"})
                if im_online:
                    manager.prepare_candidate(
                        candidate.run_id, candidate.candidate_id, key, projection
                    )
                event = {
                    "event": "assistant_message",
                    "run_id": candidate.run_id,
                    "turn_id": candidate.turn_id,
                    "message_id": candidate.candidate_id,
                    "group_id": candidate.group_id,
                    "content": candidate.text,
                    "reasoning_content": "",
                    "_managed_output": True,
                    "prepared_output_key": key,
                    "origin": candidate.metadata.get("run_origin"),
                    "background_returns": candidate.metadata.get(
                        "source_background_returns", []
                    ),
                }
                pending = self.writer(event)
                if pending is not None:
                    await pending
                im_receipt = self.ledger.delivery_receipt(key, "im")
                if im_online and (
                    not im_receipt or im_receipt.get("state") != "delivered"
                ):
                    raise ConnectionError("IM message receipt was not confirmed")
            if im_receipt and im_receipt.get("state") == "delivered":
                receipts.append({"channel": "im", **im_receipt})
            if external is not None:
                outbound, resources = external
                channel = outbound.channel_name
                receipt = self.ledger.delivery_receipt(key, channel)
                if receipt is None or receipt.get("state") != "delivered":
                    await self._commit_publication(
                        key, channel, external_recovery_payload(outbound, resources)
                    )
                    receipt = self.ledger.delivery_receipt(key, channel)
                receipts.append({"channel": channel, **receipt})
            if not im_online:
                context.image_delivery_pending = True
                self.notify_pending()
                return DeliveryResult(
                    state="partial" if receipts else "pending",
                    delivery_id=key,
                    reason_code="im_offline",
                    diagnostic="The external channel received this image reply; the IM shadow is awaiting synchronization. Do not resend the reply."
                    if receipts
                    else "Delivery is awaiting IM synchronization. Do not resend this candidate.",
                    channel_receipts=tuple(receipts),
                )
            return DeliveryResult(
                state="delivered", delivery_id=key, channel_receipts=tuple(receipts)
            )
        except Exception as exc:
            context.image_delivery_pending = True
            self.notify_pending()
            return DeliveryResult(
                state="partial" if receipts else "pending",
                reason_code="delivery_unconfirmed",
                diagnostic=f"Image delivery {key} is partially confirmed or awaiting confirmation ({type(exc).__name__}). Do not resend this candidate; preserve its receipts for reconciliation.",
                delivery_id=key,
                channel_receipts=tuple(receipts),
            )
        finally:
            self.tracker.release_publication(candidate.run_id)

    async def recover_pending(self, *, limit=100):
        """Reconcile saved publication identities and immutable provider resources."""
        async with self._recovery_lock:
            return await self._recover(limit=limit)

    async def _commit_publication(
        self, output_key, channel, recovery, *, recovering=False
    ):
        lock = self._publication_locks.setdefault((output_key, channel), asyncio.Lock())
        async with lock:
            return await self._commit_publication_unlocked(
                output_key, channel, recovery, recovering=recovering
            )

    async def _commit_publication_unlocked(
        self, output_key, channel, recovery, *, recovering=False
    ):
        """Send or recover one fixed destination through the same durable commit path."""
        latest = self.ledger.delivery_receipt(output_key, channel) or {}
        if latest.get("state", latest.get("status")) == "delivered":
            if recovery["kind"] == "explicit_message":
                from personal_assistant.ws.im_connection import IMDispatchAck

                return IMDispatchAck.from_payload(latest["ack"])
            return latest
        self.ledger.record_delivery(
            output_key,
            channel,
            {**latest, "state": "pending", "status": "unknown", "recovery": recovery},
        )
        latest = self.ledger.delivery_receipt(output_key, channel)
        kind = recovery["kind"]
        if kind == "explicit_message":
            result = await self.connection.send_agent_message(recovery["payload"])
            confirmed = {"ack": result.as_dict(), "message_id": result.message_id}
        elif kind == "native_delta":
            result = await self.connection.send_json_await_ack(
                recovery.get("message_type", "node.streaming_delta"),
                recovery["payload"],
            )
            if result is None:
                raise ConnectionError("IM message receipt was not confirmed")
            completion = recovery.get("completion_payload")
            run_id = str(recovery["payload"].get("run_id") or "")
            if (
                recovering
                and completion is not None
                and self.contexts.get(run_id) is None
            ):
                ack = await self.connection.send_json_await_ack(
                    "node.streaming_delta", completion
                )
                if ack is None:
                    raise ConnectionError("IM completion receipt was not confirmed")
            confirmed = {
                "message_id": recovery["payload"].get("message_id"),
                "conversation_id": recovery["payload"].get("conversation_id"),
            }
        elif kind == "external_prepared":
            if not external_retry_allowed(latest):
                raise ConnectionError("Provider deduplication window expired")
            saved = recovery["preparation"]
            preparation = ProviderImagePreparation(
                connector_account_id=saved["connector_account_id"],
                app_id=saved["app_id"],
                entries=tuple(
                    ProviderImageEntry(**entry) for entry in saved["entries"]
                ),
            )
            result = await self.router.send_prepared_async(
                OutboundMessage(**recovery["outbound"]),
                preparation,
                before_publish=lambda: external_retry_allowed(latest),
            )
            if result != "delivered":
                raise ConnectionError("External delivery was not confirmed")
            confirmed = {"message_id": getattr(result, "message_id", None)}
        else:
            raise ValueError(f"Unknown publication kind: {kind}")
        self.ledger.record_delivery(
            output_key,
            channel,
            {**latest, **confirmed, "state": "delivered", "status": "delivered"},
        )
        return result

    async def _recover(self, *, limit):
        delivered = 0
        for output_key, channel, receipt in self.ledger.unresolved_deliveries(
            limit=limit
        ):
            try:
                await self._commit_publication(
                    output_key, channel, receipt["recovery"], recovering=True
                )
                delivered += 1
            except Exception:
                continue
        return delivered

    def next_submission(self, logical_request_id):
        return self.ledger.next_submission(logical_request_id)

    def record_admitted(self, logical_request_id, submission_id):
        self.ledger.record_admitted(logical_request_id, submission_id)

    async def prepare_outbound(
        self, outbound: OutboundMessage
    ) -> PreparedOutbound | None:
        run_id = str(outbound.metadata.get("run_id") or "")
        if not run_id:
            return None
        context = self.contexts.get(run_id)
        if context is None:
            return PreparedOutbound(
                outbound, lambda _: None, lambda: False, lambda: None, lambda: None
            )
        self.contexts.retain(run_id)
        try:
            output_key = str(
                outbound.metadata.get("output_key") or context.reply_output_key
            )
            prepared = await asyncio.to_thread(
                self.images.prepare,
                self.image_context(context.agent_id, run_id, output_key, output_key),
                outbound.text,
            )
            adapter = self.registry.get(outbound.channel_name)
            images = await asyncio.to_thread(
                self.images.outbound_images, prepared, adapter.image_account_id
            )
            loop = asyncio.get_running_loop()

            def before() -> bool:
                return asyncio.run_coroutine_threadsafe(
                    self.admit(run_id), loop
                ).result()

            async def release_admission() -> None:
                self.tracker.release_publication(run_id)

            def after() -> None:
                asyncio.run_coroutine_threadsafe(release_admission(), loop).result()

            return PreparedOutbound(
                replace(outbound, text=prepared.markdown_template, images=images),
                lambda receipt: self.images.record_provider_receipts(
                    output_key, receipt
                ),
                before,
                after,
                lambda: self.contexts.release(run_id),
            )
        except BaseException:
            self.contexts.release(run_id)
            raise

    def native_confirmed(self, output_key):
        receipt = self.ledger.delivery_receipt(output_key, "im")
        return bool(
            receipt and receipt.get("state", receipt.get("status")) == "delivered"
        )

    async def publish_native_frame(
        self, output_key, message_type, payload, completion_payload
    ):
        """Record the native frame before awaiting its acknowledgement."""
        recovery = {
            "kind": "native_delta",
            "message_type": message_type,
            "payload": dict(payload),
            "completion_payload": completion_payload,
        }
        return await self._commit_publication(output_key, "im", recovery)

    async def prepare_dispatch(
        self,
        dispatch: dict[str, Any],
        payload: Mapping[str, Any],
        provenance: SessionProvenance | None,
    ) -> PreparedReply | None:
        """Prepare all private image resources before the revision commit check."""

        prepared = None
        conversation_id = dispatch["to"]
        if has_image_references(dispatch["text"]) and (
            self.images is None or provenance is None
        ):
            raise ImageDeliveryError(
                [
                    {
                        "ordinal": 1,
                        "source": "",
                        "error_code": "delivery_context_unavailable",
                    }
                ]
            )
        if (
            has_image_references(dispatch["text"])
            and self.images is not None
            and provenance is not None
        ):
            conversation_id = await self.images.resolve_target(
                conversation_id, agent_id=provenance.agent.agent_id
            )
        if (
            self.images is not None
            and provenance is not None
            and conversation_id.startswith("c_")
        ):
            call_id = payload.get("dispatch_request_id")
            if not isinstance(call_id, str) or not call_id.strip():
                raise ValueError("reply images require a stable dispatch_request_id")
            agent = provenance.agent
            output_key = (
                f"dispatch:{agent.agent_id}:{provenance.kernel_session_id}:{call_id}"
            )
            prepared = await asyncio.to_thread(
                self.images.prepare,
                ReplyImageContext(
                    output_key=output_key,
                    owner_id=self.owner_id,
                    agent_id=agent.agent_id,
                    run_id=str(payload.get("origin_run_id") or ""),
                    bubble_id=call_id,
                    workspace=agent.config.workspace_root,
                ),
                dispatch["text"],
                im_conversation_id=conversation_id,
            )
            dispatch["text"] = await self.images.project_im(
                prepared, conversation_id, agent_id=agent.agent_id
            )
        return prepared

    async def send_im_dispatch(
        self,
        dispatch: dict[str, Any],
        payload: Mapping[str, Any],
        provenance: SessionProvenance | None,
        prepared: PreparedReply | None = None,
    ) -> tuple[Any, PreparedReply | None]:
        """Publish only prepared content after the caller's revision guard."""
        if prepared is not None and prepared.images:
            channel = f"im:{dispatch['to']}"
            recovery = {"kind": "explicit_message", "payload": dict(dispatch)}
            try:
                ack = await self._commit_publication(
                    prepared.output_key, channel, recovery
                )
            except Exception:
                ack = await self._commit_publication(
                    prepared.output_key, channel, recovery
                )
        else:
            ack = await self.connection.send_agent_message(dispatch)
        return ack, prepared

    async def prepare_dispatch_external(
        self, prepared, metadata, dispatch_event_id, channel
    ):
        channel_name = metadata.get("channel_name")
        if (
            prepared is None
            or not prepared.images
            or not channel_name
            or channel_name == "web_relay"
        ):
            return None
        receipt = self.ledger.delivery_receipt(prepared.output_key, channel)
        if receipt and receipt.get("status", receipt.get("state")) == "delivered":
            return None
        adapter = self.registry.get(channel_name)
        result = await self.router.prepare_images_async(
            text=prepared.markdown_template,
            reply_context=ReplyContext(
                channel_name=channel_name,
                target_chat_id=metadata["target_chat_id"],
                thread_id=metadata.get("thread_id"),
                metadata={
                    **metadata.get("metadata", {}),
                    "reply_dedupe_key": dispatch_event_id,
                },
            ),
            images=await asyncio.to_thread(
                self.images.outbound_images, prepared, adapter.image_account_id
            ),
            record_provider_receipts=lambda value: self.images.record_provider_receipts(
                prepared.output_key, value
            ),
        )
        self.ledger.record_delivery(
            prepared.output_key,
            channel,
            {"status": "unknown", "recovery": external_recovery_payload(*result)},
        )
        return result

    async def publish_dispatch_external(
        self, prepared, external, channel, metadata, event_id, text
    ):
        if prepared is not None and prepared.images:
            if external is None:
                return
            await self._commit_publication(
                prepared.output_key, channel, external_recovery_payload(*external)
            )
        else:
            await self.router.send_text_async(
                text=text,
                reply_context=ReplyContext(
                    channel_name=metadata["channel_name"],
                    target_chat_id=metadata["target_chat_id"],
                    thread_id=metadata.get("thread_id"),
                    metadata={
                        **metadata.get("metadata", {}),
                        "reply_dedupe_key": event_id,
                    },
                ),
            )

    async def project_saved_shadow(
        self, output_key, conversation_id, agent_id, content
    ):
        """Project only an approved saved snapshot when a shadow gains an anchor."""
        prepared = await asyncio.to_thread(self.images.load, output_key)
        if prepared is None:
            if has_image_references(content):
                raise ImageDeliveryError(
                    [{"ordinal": 1, "source": "", "error_code": "snapshot_unavailable"}]
                )
            return content
        return await self.images.project_im(
            prepared, conversation_id, agent_id=agent_id
        )

    async def mirror_shadow_output(self, shadow, saga, output) -> None:
        shadow_ref = saga.shadow_ref
        if shadow_ref is None:
            raise ValueError("shadow output requires a confirmed user anchor")
        content = await self.project_saved_shadow(
            output.output_key, shadow_ref.conversation_id, saga.agent_id, output.content
        )
        token = await shadow._require_gateway_token()
        async with httpx.AsyncClient(
            base_url=shadow._base_url,
            headers=build_im_http_headers(token),
            timeout=shadow._timeout_seconds,
            trust_env=False,
            transport=shadow._transport,
        ) as client:
            if shadow._before_publish is not None and not await shadow._before_publish(
                output.run_id
            ):
                assert shadow._saga_store is not None
                shadow._saga_store.discard_output(output)
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
                if shadow._after_publish is not None:
                    shadow._after_publish(output.run_id)
            message_id = str(response.json().get("id") or "").strip()
            if not message_id:
                raise ValueError("external shadow agent message response missing id")
        saga_store = shadow._saga_store
        assert saga_store is not None
        saga_store.record_output_anchor(output=output, im_message_id=message_id)

        self.ledger.record_delivery(
            output.output_key,
            "im",
            {"state": "delivered", "conversation_id": shadow_ref.conversation_id},
        )

    async def reconcile_shadow_snapshot(self, shadow, snapshot) -> None:
        """Reconcile one terminal rich snapshot into its same-identity IM row."""

        saga_store = shadow._saga_store
        if saga_store is None:
            raise RuntimeError("external shadow bubble requires durable saga storage")
        saga = saga_store.require(snapshot.saga_id)
        shadow_ref = saga.shadow_ref
        if shadow_ref is None:
            return
        content = await self.project_saved_shadow(
            snapshot.output_key,
            shadow_ref.conversation_id,
            saga.agent_id,
            snapshot.content,
        )
        token = await shadow._require_gateway_token()
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
            base_url=shadow._base_url,
            headers=build_im_http_headers(token),
            timeout=shadow._timeout_seconds,
            trust_env=False,
            transport=shadow._transport,
        ) as client:
            if shadow._before_publish is not None and not await shadow._before_publish(
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
                if shadow._after_publish is not None:
                    shadow._after_publish(snapshot.run_id)
            message_id = str(response.json().get("id") or "").strip()
            if not message_id:
                raise ValueError("external shadow reconcile response missing id")
        saga_store.acknowledge(
            shadow_message_id=snapshot.shadow_message_id,
            im_message_id=message_id,
        )

        self.ledger.record_delivery(
            snapshot.output_key,
            "im",
            {
                "state": "delivered",
                "message_id": message_id,
                "conversation_id": shadow_ref.conversation_id,
            },
        )
