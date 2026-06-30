"""Feishu channel adapter for the Node Gateway.

Implements the ``ChannelAdapter`` protocol, bridging feishu message events
(1:1 DM and group @Bot) into the gateway inbound pipeline.  Uses
``FeishuClient`` for SDK connectivity and ``GroupContextStore`` for buffering
non-mention group messages as conversation context.
"""

from __future__ import annotations

import logging
from typing import Any

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


class FeishuAdapter:
    """Feishu channel adapter implementing the ChannelAdapter Protocol.

    Args:
        app_id: Feishu application ID.
        app_secret: Feishu application secret.
        agent_id: Gateway agent this bot is bound to.
        bot_open_id: Feishu open_id of this bot, used for @mention detection.
            When ``None``, group messages without explicit mentions will all be
            buffered (safe default).
        group_context_store: Shared buffer for non-mention group messages.
        domain: Feishu API domain (default ``https://open.feishu.cn``).
    """

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        agent_id: str,
        bot_open_id: str | None = None,
        group_context_store: GroupContextStore,
        domain: str = "https://open.feishu.cn",
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._agent_id = agent_id
        self._bot_open_id = bot_open_id
        self._group_ctx = group_context_store
        self._domain = domain
        self._client: FeishuClient | None = None
        self._on_inbound: InboundHandler | None = None

    @property
    def name(self) -> str:
        return f"feishu:{self._agent_id}"

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

        try:
            self._client.send_message(
                receive_id=receive_id,
                text=outbound.text,
                receive_id_type="chat_id",
            )
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
        - Group + @Bot → flush context buffer + deliver
        - Group + no @Bot (or @所有人) → push to context buffer
        """
        if self._on_inbound is None:
            return

        if not event.is_group:
            self._deliver_dm(event)
            return

        if _is_bot_mentioned(event.mentions, self._bot_open_id):
            self._deliver_group_with_context(event)
        else:
            self._buffer_group_message(event)

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
            },
        )
        assert self._on_inbound is not None
        self._on_inbound(inbound)

    def _deliver_group_with_context(self, event: FeishuMessageEvent) -> None:
        """Flush buffered context and deliver a group @Bot message."""
        buf_key = _group_buf_key(self._app_id, self._agent_id, event.chat_id)
        buffered = self._group_ctx.drain(buf_key)

        # Prepend buffered context as "[sender] text" lines
        context_lines: list[str] = []
        for sender, text in buffered:
            context_lines.append(f"[{sender}] {text}")

        full_text = event.text
        if context_lines:
            context_prefix = "\n".join(context_lines)
            full_text = f"(previous messages)\n{context_prefix}\n\n{full_text}"

        inbound = InboundMessage(
            channel_name=self.name,
            text=full_text,
            external_user_id=event.sender_open_id,
            external_chat_id=f"feishu:{self._app_id}:group:{event.chat_id}",
            is_group=True,
            agent_id=self._agent_id,
            metadata={
                "feishu_message_id": event.message_id,
                "feishu_chat_type": event.chat_type,
                "feishu_mentions": [
                    {"open_id": m.open_id, "name": m.name, "key": m.key}
                    for m in event.mentions
                ],
            },
        )
        assert self._on_inbound is not None
        self._on_inbound(inbound)

    def _buffer_group_message(self, event: FeishuMessageEvent) -> None:
        """Push a non-@Bot group message into the context buffer."""
        buf_key = _group_buf_key(self._app_id, self._agent_id, event.chat_id)
        self._group_ctx.append(buf_key, event.text, sender=event.sender_open_id)
        logger.debug(
            "buffered group message for %s: %s", buf_key, event.text[:50]
        )


def _is_bot_mentioned(
    mentions: list[FeishuMention], bot_open_id: str | None
) -> bool:
    """Check if the bot is explicitly mentioned in the message.

    Returns True when:
    - bot_open_id is set and appears in the mentions list
    - bot_open_id is None and any non-@所有人 mention exists (conservative: trigger)

    Returns False when:
    - No mentions at all
    - Only @所有人 (open_id="all") is mentioned
    """
    if not mentions:
        return False

    if bot_open_id is None:
        # No bot_open_id configured — any real mention triggers
        return any(m.open_id != "all" for m in mentions)

    return any(m.open_id == bot_open_id for m in mentions)


def _group_buf_key(app_id: str, agent_id: str, chat_id: str) -> str:
    """Build the GroupContextStore buffer key for a feishu group chat."""
    return f"feishu:{app_id}:{chat_id}:{agent_id}"


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
