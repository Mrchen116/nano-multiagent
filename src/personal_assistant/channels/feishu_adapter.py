"""Feishu channel adapter for the Node Gateway.

Implements the ``ChannelAdapter`` protocol, bridging feishu message events
(1:1 DM and group chat) into the gateway inbound pipeline.  Uses
``FeishuClient`` for SDK connectivity. Current group messages are delivered with
structured mention metadata so the gateway pipeline owns reply-policy gating,
buffering, and IM shadow sync.
"""

from __future__ import annotations

import logging
import threading

from personal_assistant.channels.base import (
    InboundHandler,
    InboundMessage,
    OutboundMessage,
)
from personal_assistant.channels.feishu_client import (
    FeishuAPIError,
    FeishuAuthError,
    FeishuClient,
    FeishuMessageEvent,
    FeishuMention,
)
from personal_assistant.gateway.group_context_store import GroupContextStore

logger = logging.getLogger(__name__)

_ACK_REACTION_EMOJI_TYPE = "THINKING"
_GROUP_MESSAGE_SCOPE = "im:message.group_msg"


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
        group_context_store: GroupContextStore,
        domain: str = "https://open.feishu.cn",
    ) -> None:
        self._name = name
        self._app_id = app_id
        self._app_secret = app_secret
        self._agent_id = _parse_agent_id_from_name(name)
        self._bot_open_id = bot_open_id
        self._owner_open_id = owner_open_id
        self._group_ctx = group_context_store
        self._domain = domain
        self._client: FeishuClient | None = None
        self._on_inbound: InboundHandler | None = None
        self._ack_reactions: dict[str, str] = {}
        self._ack_reactions_lock = threading.Lock()
        self._seen_group_message_ids: dict[str, dict[str, None]] = {}

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
        )
        self._client.start(self._handle_message)
        self._warn_if_group_message_scope_missing()
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
            if not message.text.strip():
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
            self._seen_group_message_ids[event.chat_id] = dict(list(seen.items())[-250:])

    def _is_self_sender(self, event: FeishuMessageEvent) -> bool:
        return event.sender_open_id in {self._bot_open_id, self._app_id}

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
        if reply_phase not in {"final", "terminal"}:
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
        inbound = InboundMessage(
            channel_name=self.name,
            text=event.text,
            external_user_id=event.sender_open_id,
            external_chat_id=f"feishu:{self._app_id}:dm:{event.sender_open_id}",
            is_group=False,
            agent_id=self._agent_id,
            metadata={
                "feishu_message_id": event.message_id,
                "feishu_chat_type": event.chat_type,
                "feishu_mentions": [
                    {"open_id": m.open_id, "name": m.name, "key": m.key}
                    for m in event.mentions
                ],
                "raw_text": event.raw_text,
                "mention_only": event.mention_only,
                **self._external_metadata(event, is_group=False),
            },
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
            **self._external_metadata(event, is_group=True, chat_name=chat_name),
        }
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
            metadata=metadata,
        )
        assert self._on_inbound is not None
        self._on_inbound(inbound)

    def _external_metadata(
        self,
        event: FeishuMessageEvent,
        *,
        is_group: bool,
        chat_name: str | None = None,
    ) -> dict[str, object]:
        external_chat_id = (
            f"feishu:{self._app_id}:group:{event.chat_id}"
            if is_group
            else f"feishu:{self._app_id}:dm:{event.sender_open_id}"
        )
        sender_display_name = (
            "你"
            if self._owner_open_id and event.sender_open_id == self._owner_open_id
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

    def _warn_if_group_message_scope_missing(self) -> None:
        """Warn when Feishu ordinary group messages are likely unavailable."""
        if self._client is None:
            return
        try:
            has_scope = self._client.has_scope(_GROUP_MESSAGE_SCOPE)
        except (FeishuAuthError, FeishuAPIError, RuntimeError):
            logger.warning(
                "failed to verify feishu app scope %s; ordinary group messages "
                "may not be delivered unless the app has this scope and the "
                "matching event subscription is enabled",
                _GROUP_MESSAGE_SCOPE,
                exc_info=True,
                extra={
                    "error_code": "feishu_group_message_scope_check_failed",
                    "agent_id": self._agent_id,
                    "adapter": self.name,
                },
            )
            return
        if has_scope is False:
            logger.warning(
                "Feishu app for adapter %s does not appear to have scope %s; "
                "ordinary group messages will not reach the agent/IM unless "
                "the Feishu/Lark app enables this permission and subscribes to "
                "group message events.",
                self.name,
                _GROUP_MESSAGE_SCOPE,
            )
        elif has_scope is None:
            logger.warning(
                "could not verify Feishu app scope %s for adapter %s; if ordinary "
                "group messages are missing, check Feishu/Lark app permissions "
                "and event subscriptions",
                _GROUP_MESSAGE_SCOPE,
                self.name,
            )


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
