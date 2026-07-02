"""Feishu channel adapter for the Node Gateway.

Implements the ``ChannelAdapter`` protocol, bridging feishu message events
(1:1 DM and group @Bot) into the gateway inbound pipeline.  Uses
``FeishuClient`` for SDK connectivity. Non-mention group messages are delivered
as ``sync_only`` inbound messages so the gateway pipeline owns buffering and IM
shadow sync.
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


class FeishuAdapter:
    """Feishu channel adapter implementing the ChannelAdapter Protocol.

    Args:
        name: Stable channel adapter name in the form ``feishu:<agent_id>``.
            The agent id is parsed from the suffix and used for routing and
            session isolation.
        app_id: Feishu application ID.
        app_secret: Feishu application secret.
        bot_open_id: Feishu open_id of this bot, used for @mention detection.
            When ``None``, group messages without explicit mentions will all be
            buffered (safe default).
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
        - Group + @Bot → deliver
        - Group + no @Bot (or @所有人) → deliver sync_only for pipeline-owned buffer
        """
        if self._on_inbound is None:
            return

        if not event.is_group:
            self._ack_received(event)
            self._deliver_dm(event)
            return

        if _is_bot_mentioned(event.mentions, self._bot_open_id):
            self._ack_received(event)
            self._deliver_group(event, sync_only=False)
        else:
            self._deliver_group(event, sync_only=True)

    def _ack_received(self, event: FeishuMessageEvent) -> None:
        """React to a message that is about to enter the agent pipeline."""
        if self._client is None or not event.message_id:
            return
        try:
            reaction_id = self._client.add_reaction(
                message_id=event.message_id,
                emoji_type=_ACK_REACTION_EMOJI_TYPE,
            )
            if reaction_id:
                with self._ack_reactions_lock:
                    self._ack_reactions[event.message_id] = reaction_id
        except (FeishuAuthError, FeishuAPIError, RuntimeError):
            logger.warning(
                "failed to add feishu ack reaction",
                exc_info=True,
                extra={
                    "error_code": "feishu_ack_reaction_failed",
                    "message_id": event.message_id,
                    "chat_id": event.chat_id,
                    "agent_id": self._agent_id,
                    "adapter": self.name,
                },
            )

    def _remove_ack_after_reply(self, outbound: OutboundMessage) -> None:
        """Remove the ack reaction once a reply has been delivered."""
        if self._client is None:
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
                **self._external_metadata(event, is_group=False),
            },
        )
        assert self._on_inbound is not None
        self._on_inbound(inbound)

    def _deliver_group(self, event: FeishuMessageEvent, *, sync_only: bool) -> None:
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
            **self._external_metadata(event, is_group=True, chat_name=chat_name),
        }
        if sync_only:
            metadata["sync_only"] = True
        else:
            metadata["mentioned_agent_ids"] = [self._agent_id]

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
