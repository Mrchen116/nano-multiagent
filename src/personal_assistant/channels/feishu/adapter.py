"""Feishu channel adapter for the Node Gateway.

Implements the ``ChannelAdapter`` protocol, bridging feishu message events
(1:1 DM and group chat) into the gateway inbound pipeline.  Uses
``FeishuClient`` for SDK connectivity. Current group messages are delivered with
structured mention metadata so the gateway pipeline owns reply-policy gating,
buffering, and IM shadow sync.
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import logging
import threading
from collections.abc import Callable, Mapping
from typing import Any

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    ExternalInboundEventIdentity,
    InboundHandler,
    InboundIngress,
    InboundMessage,
    OutboundMessage,
)
from personal_assistant.channels.feishu.approval import FeishuPermissionApprovalSurface
from personal_assistant.channels.feishu.client import (
    FeishuAPIError,
    FeishuAuthError,
    FeishuCardActionEvent,
    FeishuClient,
    FeishuImageTooLargeError,
    FeishuMessageEvent,
    FeishuMention,
)
from personal_assistant.channels.feishu.worker import FeishuWorkerStatus
from personal_assistant.gateway.group_context_store import GroupContextStore

logger = logging.getLogger(__name__)

_ACK_REACTION_EMOJI_TYPE = "THINKING"


class FeishuAdapter:
    """Feishu channel adapter implementing the ChannelAdapter Protocol.

    Args:
        name: Stable channel adapter name in the form ``feishu:<agent_id>``.
            The agent id is parsed from the suffix and used for routing and
            session isolation.
        app_id: Feishu application ID.
        app_secret: Feishu application secret.
        bot_open_id: Feishu open_id of this bot, used for @mention detection.
            When ``None``, group messages carry empty mention metadata and the
            gateway group reply policy remains the final execution gate.
        owner_open_id: Feishu open_id of the IM owner. Messages from this user
            are displayed as "你" in the IM shadow conversation.
        owner_open_id_binder: Optional callback that binds the first real Feishu
            sender for this adapter and returns the effective owner open_id.
        permission_decision_callback: Optional callback that submits a Feishu
            native approval decision into the kernel permission broker.
        group_context_store: Shared buffer retained for constructor compatibility;
            buffering is owned by InboundPipeline for M7+.
        domain: Feishu API domain (default ``https://open.feishu.cn``).
    """

    def __init__(
        self,
        *,
        name: str,
        app_id: str,
        app_secret: str,
        bot_open_id: str | None = None,
        owner_open_id: str | None = None,
        owner_open_id_binder: Callable[[str, str], str | None] | None = None,
        permission_decision_callback: (
            Callable[[Mapping[str, object]], bool | None] | None
        ) = None,
        group_context_store: GroupContextStore,
        domain: str = "https://open.feishu.cn",
        worker_incarnation: str | None = None,
        status_callback: Callable[[FeishuWorkerStatus], None] | None = None,
    ) -> None:
        self._name = name
        self._app_id = app_id
        self._app_secret = app_secret
        self._agent_id = _parse_agent_id_from_name(name)
        self._bot_open_id = bot_open_id
        self._owner_open_id = owner_open_id
        self._owner_open_id_binder = owner_open_id_binder
        self._permission_decision_callback = permission_decision_callback
        self._owner_open_id_lock = threading.Lock()
        self._group_ctx = group_context_store
        self._domain = domain
        self._worker_incarnation = worker_incarnation
        self._status_callback = status_callback
        self._client: FeishuClient | None = None
        self._on_inbound: InboundHandler | None = None
        self._ack_reactions: dict[str, str] = {}
        self._ack_reactions_lock = threading.Lock()
        self._seen_group_message_ids: dict[str, dict[str, None]] = {}
        self._approval_surface = FeishuPermissionApprovalSurface(
            adapter_name=self.name,
            agent_id=self._agent_id,
            client_provider=lambda: self._client,
            owner_open_id_provider=self._current_owner_open_id,
            decision_callback=self._permission_decision_callback,
        )

    @property
    def name(self) -> str:
        return self._name

    def start(self, on_inbound: InboundHandler) -> None:
        """Start the feishu WebSocket listener and register the inbound callback."""
        self._on_inbound = on_inbound
        self._client = FeishuClient(
            app_id=self._app_id,
            app_secret=self._app_secret,
            domain=self._domain,
            worker_incarnation=self._worker_incarnation,
            status_callback=self._status_callback,
        )
        self._client.start(
            self._handle_message,
            on_card_action=self._handle_card_action,
        )
        logger.info("feishu adapter %s started", self.name)

    def send(self, outbound: OutboundMessage) -> None:
        """Send a reply message back to the feishu chat.

        Catches feishu-specific errors and logs structured context before
        re-raising, so callers get typed exceptions while ops get actionable
        logs.

        Raises:
            FeishuAuthError: When feishu returns 401/403 (credentials expired).
            FeishuAPIError: When feishu returns any other API error.
            RuntimeError: When the adapter has not been started.
        """
        if self._client is None:
            raise RuntimeError("feishu adapter is not started")
        if not outbound.text.strip():
            raise ValueError("feishu outbound text must be non-empty")

        # Extract raw feishu chat_id from external_chat_id
        # Format: "feishu:<app_id>:dm:<user_open_id>" or "feishu:<app_id>:group:<chat_id>"
        receive_id = _extract_chat_id(outbound.target_chat_id)

        # Determine receive_id_type based on chat type encoded in external_chat_id
        # Format: "feishu:<app_id>:dm:<user_open_id>" → "open_id" (DM)
        # Format: "feishu:<app_id>:group:<chat_id>" → "chat_id" (group)
        receive_id_type = "open_id" if ":dm:" in outbound.target_chat_id else "chat_id"

        try:
            self._client.send_message(
                receive_id=receive_id,
                text=outbound.text,
                receive_id_type=receive_id_type,
            )
            self._remove_ack_after_reply(outbound)
        except FeishuAuthError:
            logger.error(
                "feishu auth error — app credentials may be expired",
                extra={
                    "error_code": "feishu_auth_error",
                    "chat_id": outbound.target_chat_id,
                    "agent_id": self._agent_id,
                    "adapter": self.name,
                },
            )
            raise
        except FeishuAPIError:
            logger.error(
                "feishu API error — message send failed",
                extra={
                    "error_code": "feishu_api_error",
                    "chat_id": outbound.target_chat_id,
                    "agent_id": self._agent_id,
                    "adapter": self.name,
                },
            )
            raise

    def stop(self) -> None:
        """Stop the feishu WebSocket listener."""
        if self._client is not None:
            self._client.stop()
            self._client = None
        self._on_inbound = None
        logger.info("feishu adapter %s stopped", self.name)

    def stop_invalidated(self) -> None:
        """Drop queued input after disable/delete/credential replacement invalidation."""
        if self._client is not None:
            self._client.stop(drain=False)
            self._client = None
        self._on_inbound = None
        logger.info("invalidated feishu adapter %s stopped", self.name)

    def send_permission_request(
        self,
        *,
        target_chat_id: str,
        request: Mapping[str, Any],
        run_id: str,
    ) -> bool:
        """Send a Feishu-native tool approval card for a kernel request."""
        return self._approval_surface.send_permission_request(
            target_chat_id=target_chat_id,
            request=request,
            run_id=run_id,
        )

    def mark_permission_resolved(self, *, request_id: str, decision: str) -> bool:
        """Resolve a pending Feishu approval card after another surface answered."""
        return self._approval_surface.mark_permission_resolved(
            request_id=request_id,
            decision=decision,
        )

    def _handle_card_action(
        self, event: FeishuCardActionEvent
    ) -> Mapping[str, Any] | None:
        return self._approval_surface.handle_card_action(event)

    def _handle_message(self, event: FeishuMessageEvent) -> None:
        """Process one incoming feishu message event.

        Decision tree:
        - 1:1 DM → always deliver
        - Group + @Bot → deliver with mentioned_agent_ids
        - Group + no @Bot (or @所有人) → deliver with empty mentioned_agent_ids
        """
        if self._on_inbound is None:
            return

        if not event.is_group:
            if self._is_self_sender(event):
                return
            self._ack_received(event)
            self._deliver_dm(event)
            return

        self._deliver_group_history_before(event)
        if self._is_self_sender(event):
            return
        bot_mentioned = _is_bot_mentioned(event.mentions, self._bot_open_id)
        if bot_mentioned:
            self._ack_received(event)
        self._deliver_group(event, sync_only=False, bot_mentioned=bot_mentioned)
        self._remember_group_message(event)

    def _deliver_group_history_before(self, event: FeishuMessageEvent) -> None:
        """Best-effort catch-up for ordinary group messages missing from events."""
        if self._client is None:
            return
        try:
            messages = self._client.fetch_group_messages(chat_id=event.chat_id)
        except (FeishuAuthError, FeishuAPIError, RuntimeError) as exc:
            logger.warning(
                "failed to fetch feishu group history; ordinary group messages "
                "may be missing from IM shadow and group context",
                exc_info=True,
                extra={
                    "error_code": "feishu_group_history_fetch_failed",
                    "chat_id": event.chat_id,
                    "agent_id": self._agent_id,
                    "adapter": self.name,
                    "feishu_error_code": getattr(exc, "code", None),
                },
            )
            return

        pending: list[FeishuMessageEvent] = []
        for message in messages:
            if self._is_self_sender(message):
                pending.clear()
                continue
            pending.append(message)

        for message in pending:
            if not message.message_id or message.message_id == event.message_id:
                continue
            if not message.text.strip() and not message.image_keys:
                continue
            if self._was_group_message_seen(message):
                continue
            self._deliver_group(message, sync_only=True, source="history_catchup")
            self._remember_group_message(message)

    def _was_group_message_seen(self, event: FeishuMessageEvent) -> bool:
        return event.message_id in self._seen_group_message_ids.get(event.chat_id, {})

    def _remember_group_message(self, event: FeishuMessageEvent) -> None:
        if not event.message_id:
            return
        seen = self._seen_group_message_ids.setdefault(event.chat_id, {})
        seen[event.message_id] = None
        if len(seen) > 500:
            self._seen_group_message_ids[event.chat_id] = dict(
                list(seen.items())[-250:]
            )

    def _is_self_sender(self, event: FeishuMessageEvent) -> bool:
        sender_open_id = event.sender_open_id.strip()
        self_ids = {self._app_id}
        if self._bot_open_id:
            self_ids.add(self._bot_open_id)
        return sender_open_id in self_ids

    def _ack_received(self, event: FeishuMessageEvent) -> None:
        """React to a message that is about to enter the agent pipeline."""
        self.ack_message(event.message_id)

    def ack_message(self, message_id: str | None) -> None:
        """React to a Feishu message when Gateway has accepted it for processing."""
        if self._client is None or not message_id:
            return
        with self._ack_reactions_lock:
            if message_id in self._ack_reactions:
                return
        try:
            reaction_id = self._client.add_reaction(
                message_id=message_id,
                emoji_type=_ACK_REACTION_EMOJI_TYPE,
            )
            if reaction_id:
                with self._ack_reactions_lock:
                    self._ack_reactions[message_id] = reaction_id
        except (FeishuAuthError, FeishuAPIError, RuntimeError):
            logger.warning(
                "failed to add feishu ack reaction",
                exc_info=True,
                extra={
                    "error_code": "feishu_ack_reaction_failed",
                    "message_id": message_id,
                    "agent_id": self._agent_id,
                    "adapter": self.name,
                },
            )

    def _remove_ack_after_reply(self, outbound: OutboundMessage) -> None:
        """Remove the ack reaction once the final visible reply has been delivered."""
        if self._client is None:
            return
        reply_phase = outbound.metadata.get("reply_phase")
        if reply_phase not in {"control", "final", "terminal"}:
            return
        message_id = outbound.metadata.get("feishu_message_id")
        if not isinstance(message_id, str) or not message_id:
            return
        with self._ack_reactions_lock:
            reaction_id = self._ack_reactions.pop(message_id, None)
        if not reaction_id:
            return
        try:
            self._client.delete_reaction(
                message_id=message_id,
                reaction_id=reaction_id,
            )
        except (FeishuAuthError, FeishuAPIError, RuntimeError):
            logger.warning(
                "failed to remove feishu ack reaction",
                exc_info=True,
                extra={
                    "error_code": "feishu_ack_reaction_remove_failed",
                    "message_id": message_id,
                    "agent_id": self._agent_id,
                    "adapter": self.name,
                },
            )

    def _deliver_dm(self, event: FeishuMessageEvent) -> None:
        """Deliver a 1:1 DM as an InboundMessage."""
        attachments, image_indexes, image_failure = self._download_image_attachments(
            event
        )
        metadata: dict[str, object] = {
            "feishu_message_id": event.message_id,
            "feishu_chat_type": event.chat_type,
            "feishu_mentions": [
                {"open_id": m.open_id, "name": m.name, "key": m.key}
                for m in event.mentions
            ],
            "raw_text": event.raw_text,
            "mention_only": event.mention_only,
            **self._external_metadata(event, is_group=False),
        }
        if attachments:
            metadata["attachments"] = attachments
        if image_failure is not None:
            metadata["image_resolution_failure"] = image_failure
        kernel_parts = self._kernel_input_parts(event, image_indexes=image_indexes)
        if kernel_parts:
            metadata["kernel_input_parts"] = kernel_parts
        inbound = InboundMessage(
            channel_name=self.name,
            text=event.text,
            external_user_id=event.sender_open_id,
            external_chat_id=f"feishu:{self._app_id}:dm:{event.sender_open_id}",
            is_group=False,
            agent_id=self._agent_id,
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id=self._app_id,
                provider_event_id=event.message_id,
            ),
            ingress=self._inbound_ingress(event, is_group=False),
            metadata=metadata,
        )
        assert self._on_inbound is not None
        self._on_inbound(inbound)

    def _deliver_group(
        self,
        event: FeishuMessageEvent,
        *,
        sync_only: bool,
        bot_mentioned: bool = False,
        source: str = "event",
    ) -> None:
        """Deliver a group message and let InboundPipeline own buffering/drain."""
        external_chat_id = f"feishu:{self._app_id}:group:{event.chat_id}"
        chat_name = self._group_chat_name(event.chat_id)
        metadata = {
            "feishu_message_id": event.message_id,
            "feishu_chat_type": event.chat_type,
            "feishu_mentions": [
                {"open_id": m.open_id, "name": m.name, "key": m.key}
                for m in event.mentions
            ],
            "raw_text": event.raw_text,
            "mention_only": event.mention_only,
            "feishu_delivery_source": source,
            **self._external_metadata(
                event,
                is_group=True,
                chat_name=chat_name,
                bind_owner=source == "event",
            ),
        }
        attachments, image_indexes, image_failure = self._download_image_attachments(
            event
        )
        if attachments:
            metadata["attachments"] = attachments
        if image_failure is not None:
            metadata["image_resolution_failure"] = image_failure
        kernel_parts = self._kernel_input_parts(event, image_indexes=image_indexes)
        if kernel_parts:
            metadata["kernel_input_parts"] = kernel_parts
        if sync_only:
            metadata["sync_only"] = True
        else:
            metadata["mentioned_agent_ids"] = [self._agent_id] if bot_mentioned else []

        inbound = InboundMessage(
            channel_name=self.name,
            text=event.text,
            external_user_id=event.sender_open_id,
            external_chat_id=external_chat_id,
            is_group=True,
            agent_id=self._agent_id,
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id=self._app_id,
                provider_event_id=event.message_id,
            ),
            ingress=self._inbound_ingress(event, is_group=True),
            metadata=metadata,
        )
        assert self._on_inbound is not None
        self._on_inbound(inbound)

    def _inbound_ingress(
        self,
        event: FeishuMessageEvent,
        *,
        is_group: bool,
    ) -> InboundIngress:
        external_chat_id = (
            f"feishu:{self._app_id}:group:{event.chat_id}"
            if is_group
            else f"feishu:{self._app_id}:dm:{event.sender_open_id}"
        )
        return InboundIngress(
            external_conversation=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id=external_chat_id,
                agent_id=self._agent_id,
                conversation_type="group" if is_group else "direct",
                trigger_source="feishu",
            ),
            external_event=ExternalInboundEventIdentity(
                connector_account_id=self._app_id,
                provider_event_id=event.message_id,
            ),
        )

    def _download_image_attachments(
        self,
        event: FeishuMessageEvent,
    ) -> tuple[list[dict[str, str]], dict[str, int], str | None]:
        """Resolve Feishu image keys into the shared Gateway attachment shape."""
        if self._client is None or not event.image_keys:
            return [], {}, None
        attachments: list[dict[str, str]] = []
        image_indexes: dict[str, int] = {}
        failure: str | None = None
        image_keys = event.image_keys[:5]
        with ThreadPoolExecutor(max_workers=len(image_keys)) as executor:
            downloads = [
                (
                    image_key,
                    executor.submit(
                        self._client.download_message_image,
                        message_id=event.message_id,
                        image_key=image_key,
                    ),
                )
                for image_key in image_keys
            ]
        for image_key, download in downloads:
            try:
                resource = download.result()
            except FeishuImageTooLargeError:
                failure = "oversize"
                logger.warning(
                    "feishu message image exceeds inbound limit",
                    exc_info=True,
                    extra={
                        "error_code": "feishu_message_image_oversize",
                        "message_id": event.message_id,
                        "image_key": image_key,
                        "agent_id": self._agent_id,
                        "adapter": self.name,
                    },
                )
                continue
            except (FeishuAuthError, FeishuAPIError, RuntimeError):
                failure = failure or "download"
                logger.warning(
                    "failed to download feishu message image",
                    exc_info=True,
                    extra={
                        "error_code": "feishu_message_image_download_failed",
                        "message_id": event.message_id,
                        "image_key": image_key,
                        "agent_id": self._agent_id,
                        "adapter": self.name,
                    },
                )
                continue
            encoded = base64.b64encode(resource.data).decode("ascii")
            attachment = {
                "url": f"data:{resource.content_type};base64,{encoded}",
                "content_type": resource.content_type,
                "file_name": resource.file_name or f"{image_key}.image",
            }
            image_indexes[image_key] = len(attachments)
            attachments.append(attachment)
        return attachments, image_indexes, failure

    @staticmethod
    def _kernel_input_parts(
        event: FeishuMessageEvent,
        *,
        image_indexes: Mapping[str, int],
    ) -> list[dict[str, object]]:
        """Map provider order to text and resolved attachment references."""
        if not event.content_parts or not event.image_keys:
            return []
        parts: list[dict[str, object]] = []
        for part in event.content_parts:
            if part.kind == "text":
                if part.text:
                    parts.append({"type": "text", "text": part.text})
                continue
            attachment_index = image_indexes.get(part.image_key)
            if attachment_index is not None:
                parts.append({"type": "image", "attachment_index": attachment_index})
        return parts

    def _external_metadata(
        self,
        event: FeishuMessageEvent,
        *,
        is_group: bool,
        chat_name: str | None = None,
        bind_owner: bool = True,
    ) -> dict[str, object]:
        external_chat_id = (
            f"feishu:{self._app_id}:group:{event.chat_id}"
            if is_group
            else f"feishu:{self._app_id}:dm:{event.sender_open_id}"
        )
        owner_open_id = self._effective_owner_open_id(
            event.sender_open_id,
            bind_owner=bind_owner,
        )
        sender_display_name = (
            "你"
            if owner_open_id and event.sender_open_id == owner_open_id
            else event.sender_display_name or event.sender_open_id
        )
        metadata: dict[str, object] = {
            "external_source": "feishu",
            "external_chat_id": external_chat_id,
            "agent_id": self._agent_id,
            "trigger_source": "feishu",
            "conversation_type": "group" if is_group else "direct",
            "sender_display_name": sender_display_name,
        }
        if is_group and chat_name:
            metadata["chat_name"] = chat_name
            metadata["conversation_title"] = f"{self._agent_id} · {chat_name} · feishu"
        return metadata

    def _effective_owner_open_id(
        self, sender_open_id: str, *, bind_owner: bool
    ) -> str | None:
        with self._owner_open_id_lock:
            if self._owner_open_id:
                return self._owner_open_id
        if not bind_owner or not sender_open_id:
            return None
        binder = self._owner_open_id_binder
        if binder is None:
            return None
        bound = binder(self.name, sender_open_id)
        if not isinstance(bound, str) or not bound.strip():
            return None
        cleaned = bound.strip()
        with self._owner_open_id_lock:
            self._owner_open_id = cleaned
        return cleaned

    def _current_owner_open_id(self) -> str | None:
        with self._owner_open_id_lock:
            return self._owner_open_id

    def _group_chat_name(self, chat_id: str) -> str | None:
        if self._client is None:
            return None
        try:
            return self._client.get_chat_name(chat_id)
        except (FeishuAuthError, FeishuAPIError, RuntimeError):
            logger.warning(
                "failed to fetch feishu group chat name",
                exc_info=True,
                extra={
                    "error_code": "feishu_chat_name_lookup_failed",
                    "chat_id": chat_id,
                    "agent_id": self._agent_id,
                    "adapter": self.name,
                },
            )
            return None


def _is_bot_mentioned(mentions: list[FeishuMention], bot_open_id: str | None) -> bool:
    """Check if the bot is explicitly mentioned in the message.

    Returns True when:
    - bot_open_id is set and appears in the mentions list

    Returns False when:
    - No mentions at all
    - Only @所有人 (open_id="all") is mentioned
    - bot_open_id is missing, because another human/bot mention is not proof that
      this adapter was addressed
    """
    if not mentions:
        return False

    if bot_open_id is None:
        return False

    return any(m.open_id == bot_open_id for m in mentions)


def _extract_chat_id(external_chat_id: str) -> str:
    """Extract the raw feishu chat_id from an external_chat_id string.

    Formats:
    - ``feishu:<app_id>:dm:<user_open_id>`` → ``<user_open_id>``
    - ``feishu:<app_id>:group:<chat_id>`` → ``<chat_id>``

    For DMs the "receive_id" is the user's open_id (feishu routes to the DM).
    For groups it's the chat_id.
    """
    parts = external_chat_id.split(":")
    if len(parts) >= 4:
        return parts[-1]
    return external_chat_id


def _parse_agent_id_from_name(name: str) -> str:
    """Parse the agent id from a feishu channel name.

    Args:
        name: Channel name in the form ``feishu:<agent_id>``.

    Returns:
        The ``agent_id`` suffix.

    Raises:
        ValueError: When the name is not a valid feishu channel name.
    """
    if not name.startswith("feishu:"):
        raise ValueError(f"invalid feishu channel name: {name}")
    agent_id = name[len("feishu:") :]
    if not agent_id:
        raise ValueError(f"feishu channel name missing agent id: {name}")
    return agent_id
