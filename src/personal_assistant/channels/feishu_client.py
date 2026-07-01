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
)
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as WSClient

logger = logging.getLogger(__name__)

# Regex-free mention placeholder prefix used by feishu JSON text content.
# Feishu encodes @mentions as @_user_N placeholders inside {"text": "..."}.
_MENTION_PLACEHOLDER_PREFIX = "@_user_"

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
        text: Plain-text content with @mention placeholders stripped.
        sender_open_id: Feishu open_id of the message sender.
        chat_id: Feishu chat identifier (``oc_xxx``).
        chat_type: ``p2p`` or ``group``.
        message_id: Feishu message identifier for reply threading.
        is_group: Convenience flag derived from chat_type.
        mentions: List of @mention entities found in the message.
    """

    text: str
    sender_open_id: str
    chat_id: str
    chat_type: str
    message_id: str
    is_group: bool
    mentions: list[FeishuMention]


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

        self._rest_client = lark.Client.builder() \
            .app_id(self._app_id) \
            .app_secret(self._app_secret) \
            .domain(self._domain) \
            .build()

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
        body = CreateMessageRequestBody.builder() \
            .receive_id(receive_id) \
            .msg_type("text") \
            .content(content) \
            .build()
        request = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(body) \
            .build()

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
                        code, backoff, rate_limit_attempt, max_rate_limit_attempts,
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
        body = CreateMessageReactionRequestBody.builder() \
            .reaction_type(reaction_type) \
            .build()
        request = CreateMessageReactionRequest.builder() \
            .message_id(message_id) \
            .request_body(body) \
            .build()

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

        request = DeleteMessageReactionRequest.builder() \
            .message_id(message_id) \
            .reaction_id(reaction_id) \
            .build()

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
    message = event.event.message
    chat_id: str = message.chat_id or ""
    chat_type: str = message.chat_type or "p2p"
    message_id: str = message.message_id or ""
    raw_content: str = message.content or ""

    # Parse text from feishu JSON content {"text": "..."}
    text = _extract_text(raw_content)

    # Parse mentions — strip placeholder keys from the visible text
    mentions = _extract_mentions(message)
    for m in mentions:
        text = text.replace(m.key, "").strip()

    # Collapse multiple spaces left by removed placeholders
    while "  " in text:
        text = text.replace("  ", " ")
    text = text.strip()

    return FeishuMessageEvent(
        text=text,
        sender_open_id=sender_open_id,
        chat_id=chat_id,
        chat_type=chat_type,
        message_id=message_id,
        is_group=chat_type != "p2p",
        mentions=mentions,
    )


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
