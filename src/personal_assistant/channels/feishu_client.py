"""Feishu SDK wrapper — WebSocket event receiver + REST message sender.

Wraps ``lark-oapi`` WSClient (event subscription) and Client (REST send)
into a single lifecycle-managed object consumed by FeishuAdapter.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageReactionRequest,
    CreateMessageReactionRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
    DeleteMessageReactionRequest,
    Emoji,
    GetChatRequest,
    ListMessageRequest,
)
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as WSClient

logger = logging.getLogger(__name__)

# Regex-free mention placeholder prefix used by feishu JSON text content.
# Feishu encodes @mentions as @_user_N placeholders inside {"text": "..."}.
_MENTION_PLACEHOLDER_PREFIX = "@_user_"
_ALL_MENTION_PLACEHOLDER = "@_all"

# Retry policy constants for send_message error handling.
_MAX_RATE_LIMIT_RETRIES = 3  # Total attempts for 429 (original + 2 retries)
_SERVER_ERROR_RETRIES = 2  # Total attempts for 5xx (original + 1 retry)
_BACKOFF_BASE_SECONDS = 0.5  # Initial backoff delay for rate-limit retries

# Error code classification for feishu API responses.
_RATE_LIMIT_CODES = {429}
_AUTH_ERROR_CODES = {401, 403}
_SERVER_ERROR_CODES = set(range(500, 600))


class FeishuAPIError(Exception):
    """Feishu API returned an unrecoverable error.

    Args:
        message: Human-readable error description.
        code: Feishu API error code or HTTP status code.
    """

    def __init__(self, message: str, *, code: int) -> None:
        super().__init__(message)
        self.code = code


class FeishuAuthError(FeishuAPIError):
    """Feishu API returned an authentication/authorization error (401/403).

    Indicates the app credentials are invalid or the token has expired.
    """


@dataclass(frozen=True, slots=True)
class FeishuMention:
    """One @mention extracted from a feishu message event.

    Args:
        open_id: Feishu open_id of the mentioned entity.
        name: Display name of the mentioned entity.
        key: Placeholder key (``@_user_1``) used in the text content.
    """

    open_id: str
    name: str
    key: str


@dataclass(frozen=True, slots=True)
class FeishuMessageEvent:
    """Parsed feishu message event ready for adapter consumption.

    Args:
        text: User-visible text with @mention placeholders normalized.
        sender_open_id: Feishu open_id of the message sender.
        chat_id: Feishu chat identifier (``oc_xxx``).
        chat_type: ``p2p`` or ``group``.
        message_id: Feishu message identifier for reply threading.
        is_group: Convenience flag derived from chat_type.
        mentions: List of @mention entities found in the message.
        sender_display_name: Optional display name reported by Feishu for the sender.
        raw_text: Raw extracted text before mention placeholder normalization.
        mention_only: Whether the message contains mentions but no non-mention text.
    """

    text: str
    sender_open_id: str
    chat_id: str
    chat_type: str
    message_id: str
    is_group: bool
    mentions: list[FeishuMention]
    sender_display_name: str | None = None
    raw_text: str = ""
    mention_only: bool = False


class FeishuClient:
    """Wrap lark-oapi WSClient + REST Client for one feishu application.

    Args:
        app_id: Feishu application ID.
        app_secret: Feishu application secret.
        domain: Feishu API domain (default ``https://open.feishu.cn``).
    """

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        domain: str = "https://open.feishu.cn",
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._domain = domain
        self._on_message: Callable[[FeishuMessageEvent], None] | None = None
        self._ws_client: WSClient | None = None
        self._rest_client: lark.Client | None = None
        self._thread: threading.Thread | None = None

    def start(self, on_message: Callable[[FeishuMessageEvent], None]) -> None:
        """Start the WebSocket listener in a background daemon thread.

        Args:
            on_message: Callback invoked for each received message event.
        """
        self._on_message = on_message

        # Build event handler — register message receive callback
        handler = (
            EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_message_event)
            .build()
        )

        self._ws_client = WSClient(
            app_id=self._app_id,
            app_secret=self._app_secret,
            event_handler=handler,
            domain=self._domain,
            auto_reconnect=True,
        )

        self._rest_client = (
            lark.Client.builder()
            .app_id(self._app_id)
            .app_secret(self._app_secret)
            .domain(self._domain)
            .build()
        )

        # WSClient.start() blocks — run in daemon thread so gateway bootstrap
        # is not blocked.
        self._thread = threading.Thread(
            target=self._ws_client.start,
            name=f"feishu-ws-{self._app_id[:8]}",
            daemon=True,
        )
        self._thread.start()
        logger.info("feishu ws client started for app %s", self._app_id[:8])

    def stop(self) -> None:
        """Stop the WebSocket listener and release resources."""
        self._on_message = None
        # WSClient does not expose a clean stop(); the daemon thread will be
        # killed when the process exits. Clear references to allow GC.
        self._ws_client = None
        self._rest_client = None
        logger.info("feishu ws client stopped for app %s", self._app_id[:8])

    def send_message(
        self,
        *,
        receive_id: str,
        text: str,
        receive_id_type: str = "chat_id",
    ) -> None:
        """Send a text message via feishu REST API with error classification.

        Error handling strategy:
        - 429 (rate limit): exponential backoff retry, max 3 attempts
        - 401/403 (auth): raise FeishuAuthError immediately, no retry
        - 5xx (server): retry once
        - Other errors: raise FeishuAPIError immediately

        Args:
            receive_id: Target chat or user identifier.
            text: Plain-text message content.
            receive_id_type: Type of receive_id (``chat_id``, ``open_id``, etc.).

        Raises:
            RuntimeError: When the client has not been started.
            FeishuAuthError: When the feishu API returns 401/403.
            FeishuAPIError: When the feishu API returns any other error.
        """
        if self._rest_client is None:
            raise RuntimeError("feishu client is not started")

        content = json.dumps({"text": text})
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type("text")
            .content(content)
            .build()
        )
        request = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(body)
            .build()
        )

        max_rate_limit_attempts = _MAX_RATE_LIMIT_RETRIES
        max_server_error_attempts = _SERVER_ERROR_RETRIES
        rate_limit_attempt = 0
        server_error_attempt = 0
        rate_limit_exhausted = False
        server_error_exhausted = False

        while True:
            response = self._rest_client.im.v1.message.create(request)
            if response.success():
                return

            code: int = response.code
            msg: str = response.msg

            if code in _AUTH_ERROR_CODES:
                raise FeishuAuthError(
                    f"feishu auth error: code={code}, msg={msg}",
                    code=code,
                )

            if code in _RATE_LIMIT_CODES:
                if rate_limit_exhausted:
                    raise FeishuAPIError(
                        f"feishu rate limit exceeded after {max_rate_limit_attempts} "
                        f"attempts: code={code}, msg={msg}",
                        code=code,
                    )
                rate_limit_attempt += 1
                if rate_limit_attempt < max_rate_limit_attempts:
                    backoff = _BACKOFF_BASE_SECONDS * (2 ** (rate_limit_attempt - 1))
                    logger.warning(
                        "feishu rate limited (code=%d), retrying in %.1fs "
                        "(attempt %d/%d)",
                        code,
                        backoff,
                        rate_limit_attempt,
                        max_rate_limit_attempts,
                    )
                    time.sleep(backoff)
                    continue
                rate_limit_exhausted = True
                continue

            if code in _SERVER_ERROR_CODES:
                if server_error_exhausted:
                    raise FeishuAPIError(
                        f"feishu server error: code={code}, msg={msg}",
                        code=code,
                    )
                server_error_attempt += 1
                if server_error_attempt < max_server_error_attempts:
                    logger.warning(
                        "feishu server error (code=%d), retrying once",
                        code,
                    )
                    time.sleep(_BACKOFF_BASE_SECONDS)
                    continue
                server_error_exhausted = True
                continue

            # Non-retryable error
            raise FeishuAPIError(
                f"feishu API error: code={code}, msg={msg}",
                code=code,
            )

    def fetch_group_messages(
        self,
        *,
        chat_id: str,
        page_size: int = 50,
    ) -> list[FeishuMessageEvent]:
        """Fetch recent group chat messages visible to the bot identity.

        This is used as a compensation path for Feishu/Lark app configurations
        where ``im.message.receive_v1`` delivers mention-class events but omits
        ordinary group messages. It requires the app/bot to have the associated
        group-message read capability; missing permission is surfaced as
        ``FeishuAPIError`` with the platform code.
        """
        if self._rest_client is None:
            raise RuntimeError("feishu client is not started")
        request = (
            ListMessageRequest.builder()
            .container_id_type("chat")
            .container_id(chat_id)
            .page_size(page_size)
            .sort_type("ByCreateTimeAsc")
            .build()
        )
        response = self._rest_client.im.v1.message.list(request)
        if not response.success():
            code: int = response.code
            msg: str = response.msg
            if code in _AUTH_ERROR_CODES:
                raise FeishuAuthError(
                    f"feishu auth error while listing group messages: "
                    f"code={code}, msg={msg}",
                    code=code,
                )
            raise FeishuAPIError(
                f"feishu API error while listing group messages: "
                f"code={code}, msg={msg}",
                code=code,
            )
        items = getattr(response.data, "items", None) or []
        return [
            _parse_feishu_history_message(item, chat_id=chat_id)
            for item in items
            if _message_type(item) == "text"
        ]

    def add_reaction(
        self, *, message_id: str, emoji_type: str = "THINKING"
    ) -> str | None:
        """Add a reaction to an inbound feishu message.

        Args:
            message_id: Feishu message identifier to react to.
            emoji_type: Feishu emoji type name, for example ``THINKING``.

        Returns:
            Feishu reaction id when the API returns one. ``None`` when
            ``message_id`` is empty or the response omits ``reaction_id``.

        Raises:
            RuntimeError: When the client has not been started.
            FeishuAuthError: When the feishu API returns 401/403.
            FeishuAPIError: When the feishu API returns any other error.
        """
        if self._rest_client is None:
            raise RuntimeError("feishu client is not started")
        if not message_id:
            return

        reaction_type = Emoji.builder().emoji_type(emoji_type).build()
        body = (
            CreateMessageReactionRequestBody.builder()
            .reaction_type(reaction_type)
            .build()
        )
        request = (
            CreateMessageReactionRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )

        response = self._rest_client.im.v1.message_reaction.create(request)
        if response.success():
            data = getattr(response, "data", None)
            reaction_id = getattr(data, "reaction_id", None)
            return str(reaction_id) if reaction_id else None

        code: int = response.code
        msg: str = response.msg
        if code in _AUTH_ERROR_CODES:
            raise FeishuAuthError(
                f"feishu auth error while adding reaction: code={code}, msg={msg}",
                code=code,
            )
        raise FeishuAPIError(
            f"feishu reaction API error: code={code}, msg={msg}",
            code=code,
        )

    def get_chat_name(self, chat_id: str) -> str | None:
        """Return the display name for a feishu group chat.

        Args:
            chat_id: Feishu group chat id (``oc_xxx``).

        Returns:
            The group name when Feishu returns one, otherwise ``None``.

        Raises:
            RuntimeError: When the client has not been started.
            FeishuAuthError: When feishu returns 401/403.
            FeishuAPIError: When feishu returns any other API error.
        """
        if self._rest_client is None:
            raise RuntimeError("feishu client is not started")

        request = GetChatRequest.builder().chat_id(chat_id).build()
        response = self._rest_client.im.v1.chat.get(request)
        if response.success():
            data = getattr(response, "data", None)
            name = getattr(data, "name", None)
            if name is None:
                return None
            chat_name = str(name).strip()
            return chat_name or None

        code: int = response.code
        msg: str = response.msg
        if code in _AUTH_ERROR_CODES:
            raise FeishuAuthError(
                f"feishu auth error while fetching chat name: code={code}, msg={msg}",
                code=code,
            )
        raise FeishuAPIError(
            f"feishu API error while fetching chat name: code={code}, msg={msg}",
            code=code,
        )

    def delete_reaction(self, *, message_id: str, reaction_id: str) -> None:
        """Delete one reaction previously added to a feishu message.

        Args:
            message_id: Feishu message identifier that carries the reaction.
            reaction_id: Feishu reaction identifier returned by ``add_reaction``.

        Raises:
            RuntimeError: When the client has not been started.
            FeishuAuthError: When the feishu API returns 401/403.
            FeishuAPIError: When the feishu API returns any other error.
        """
        if self._rest_client is None:
            raise RuntimeError("feishu client is not started")
        if not message_id or not reaction_id:
            return

        request = (
            DeleteMessageReactionRequest.builder()
            .message_id(message_id)
            .reaction_id(reaction_id)
            .build()
        )

        response = self._rest_client.im.v1.message_reaction.delete(request)
        if response.success():
            return

        code: int = response.code
        msg: str = response.msg
        if code in _AUTH_ERROR_CODES:
            raise FeishuAuthError(
                f"feishu auth error while deleting reaction: code={code}, msg={msg}",
                code=code,
            )
        raise FeishuAPIError(
            f"feishu reaction delete API error: code={code}, msg={msg}",
            code=code,
        )

    def _handle_message_event(self, event: Any) -> None:
        """Internal callback registered on the lark-oapi event dispatcher."""
        try:
            parsed = _parse_feishu_event(event)
            if self._on_message is not None:
                self._on_message(parsed)
        except Exception:
            logger.exception("failed to handle feishu message event")


def _parse_feishu_event(event: Any) -> FeishuMessageEvent:
    """Extract structured data from a P2ImMessageReceiveV1 event.

    Args:
        event: Raw P2ImMessageReceiveV1 event from lark-oapi.

    Returns:
        Parsed FeishuMessageEvent.
    """
    sender_open_id: str = event.event.sender.sender_id.open_id or ""
    sender_display_name = _extract_sender_display_name(event.event.sender)
    message = event.event.message
    chat_id: str = message.chat_id or ""
    chat_type: str = message.chat_type or "p2p"
    message_id: str = message.message_id or ""
    raw_content: str = message.content or ""

    # Parse text from feishu JSON content {"text": "..."}.
    raw_text = _extract_text(raw_content)
    mentions = _extract_mentions(message)
    text = _normalize_mention_text(raw_text, mentions)
    mention_only = bool(mentions) and _text_without_mentions(raw_text, mentions) == ""

    return FeishuMessageEvent(
        text=text,
        sender_open_id=sender_open_id,
        chat_id=chat_id,
        chat_type=chat_type,
        message_id=message_id,
        is_group=chat_type != "p2p",
        mentions=mentions,
        sender_display_name=sender_display_name,
        raw_text=raw_text,
        mention_only=mention_only,
    )


def _parse_feishu_history_message(message: Any, *, chat_id: str) -> FeishuMessageEvent:
    sender_open_id = _extract_message_sender_open_id(message)
    message_id = str(getattr(message, "message_id", "") or getattr(message, "id", ""))
    raw_content = str(getattr(message, "content", "") or "")
    raw_text = _extract_text(raw_content)
    mentions = _extract_mentions(message)
    text = _normalize_mention_text(raw_text, mentions)
    mention_only = bool(mentions) and _text_without_mentions(raw_text, mentions) == ""
    return FeishuMessageEvent(
        text=text,
        sender_open_id=sender_open_id,
        chat_id=chat_id,
        chat_type="group",
        message_id=message_id,
        is_group=True,
        mentions=mentions,
        sender_display_name=_extract_message_sender_display_name(message),
        raw_text=raw_text,
        mention_only=mention_only,
    )


def _message_type(message: Any) -> str:
    return str(getattr(message, "msg_type", "") or getattr(message, "message_type", ""))


def _extract_message_sender_open_id(message: Any) -> str:
    sender = getattr(message, "sender", None)
    if sender is None:
        return ""
    sender_id = getattr(sender, "sender_id", None)
    if sender_id is not None:
        value = getattr(sender_id, "open_id", None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    value = getattr(sender, "id", None)
    return value.strip() if isinstance(value, str) else ""


def _extract_message_sender_display_name(message: Any) -> str | None:
    sender = getattr(message, "sender", None)
    if sender is None:
        return None
    for attr in ("name", "tenant_key"):
        value = getattr(sender, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_sender_display_name(sender: Any) -> str | None:
    """Return the first non-empty Feishu sender display label available."""

    for attr in ("name", "tenant_key"):
        value = getattr(sender, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    sender_id = getattr(sender, "sender_id", None)
    if sender_id is not None:
        for attr in ("user_id", "union_id", "open_id"):
            value = getattr(sender_id, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_text(raw_content: str) -> str:
    """Extract plain text from feishu message content JSON.

    Feishu text messages have content ``{"text": "actual text"}``.
    Non-text messages (image, file, etc.) or malformed content
    are returned as-is.
    """
    if not raw_content:
        return ""
    try:
        parsed = json.loads(raw_content)
        if isinstance(parsed, dict) and "text" in parsed:
            return str(parsed["text"])
    except (json.JSONDecodeError, TypeError):
        pass
    return raw_content


def _normalize_mention_text(text: str, mentions: list[FeishuMention]) -> str:
    """Replace Feishu mention placeholders with user-visible @ labels."""

    normalized = text.replace(_ALL_MENTION_PLACEHOLDER, "@所有人")
    for mention in mentions:
        if not mention.key:
            continue
        normalized = normalized.replace(mention.key, _visible_mention_text(mention))
    return _collapse_spaces(normalized)


def _text_without_mentions(text: str, mentions: list[FeishuMention]) -> str:
    remaining = text.replace(_ALL_MENTION_PLACEHOLDER, " ")
    for mention in mentions:
        if mention.key:
            remaining = remaining.replace(mention.key, " ")
    return _collapse_spaces(remaining)


def _visible_mention_text(mention: FeishuMention) -> str:
    if mention.open_id == "all":
        label = mention.name.strip() if mention.name.strip() else "all"
    else:
        label = mention.name.strip() or mention.open_id.strip()
    if not label:
        return "@"
    if label.startswith("@"):
        return label
    return f"@{label}"


def _collapse_spaces(text: str) -> str:
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


def _extract_mentions(message: Any) -> list[FeishuMention]:
    """Extract @mention entities from a feishu event message.

    Args:
        message: EventMessage object with optional ``mentions`` list.

    Returns:
        List of FeishuMention entries.
    """
    raw_mentions = getattr(message, "mentions", None) or []
    result: list[FeishuMention] = []
    for m in raw_mentions:
        open_id = getattr(m.id, "open_id", "") if hasattr(m, "id") else ""
        name = getattr(m, "name", "") or ""
        key = getattr(m, "key", "") or ""
        if open_id:
            result.append(FeishuMention(open_id=open_id, name=name, key=key))
    return result
