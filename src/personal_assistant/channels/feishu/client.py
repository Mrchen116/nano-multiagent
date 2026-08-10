"""Feishu SDK wrapper — WebSocket event receiver + REST message sender.

Wraps ``lark-oapi`` WSClient (event subscription) and Client (REST send)
into a single lifecycle-managed object consumed by FeishuAdapter.
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import http.client
import io
import ipaddress
import json
import logging
import re
import socket
import time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Literal
from urllib.parse import SplitResult, urlsplit

import lark_oapi as lark
from lark_oapi.api.application.v6 import ListScopeRequest
from lark_oapi.api.im.v1 import (
    CreateMessageReactionRequest,
    CreateMessageReactionRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
    CreateImageRequest,
    CreateImageRequestBody,
    DeleteMessageReactionRequest,
    Emoji,
    GetChatRequest,
    GetMessageResourceRequest,
    ListMessageRequest,
    UpdateMessageRequest,
    UpdateMessageRequestBody,
)
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTriggerResponse,
)
from lark_oapi.core.enum import LogLevel
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as WSClient

from personal_assistant.channels.feishu.diagnostics import (
    FeishuDiagnostics,
    FeishuScopeProbe,
    evaluate_scope_capabilities,
    normalize_tenant_scope_grants,
    summarize_diagnostics,
)
from personal_assistant.channels.feishu.worker import (
    FeishuWorkerProcessContext,
    FeishuWorkerRuntime,
    FeishuWorkerStatus,
    FeishuWorkerStopReport,
    publish_event,
    publish_priority_status,
    publish_status,
    request_card_action,
)

logger = logging.getLogger(__name__)

# Regex-free mention placeholder prefix used by feishu JSON text content.
# Feishu encodes @mentions as @_user_N placeholders inside {"text": "..."}.
_MENTION_PLACEHOLDER_PREFIX = "@_user_"
_ALL_MENTION_PLACEHOLDER = "@_all"
_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_MAX_OUTBOUND_IMAGE_BYTES = 10 * 1024 * 1024
_MAX_INBOUND_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_OUTBOUND_IMAGE_SOURCES = 5

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


class FeishuImageTooLargeError(FeishuAPIError):
    """A Feishu message image exceeds the Gateway inbound limit."""


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
class FeishuContentPart:
    """One ordered text or image node from a Feishu message."""

    kind: Literal["text", "image"]
    text: str = ""
    image_key: str = ""


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
        image_keys: Feishu image resources carried by the message in display order.
        content_parts: Ordered provider content used to build the model's multimodal input.
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
    image_keys: tuple[str, ...] = ()
    content_parts: tuple[FeishuContentPart, ...] = ()


@dataclass(frozen=True, slots=True)
class FeishuImageResource:
    """One image downloaded from a Feishu message resource."""

    data: bytes
    content_type: str
    file_name: str | None = None


@dataclass(frozen=True, slots=True)
class FeishuCardActionEvent:
    """Parsed Feishu interactive-card action callback."""

    action_value: dict[str, Any]
    operator_open_id: str
    operator_user_id: str
    open_chat_id: str
    form_value: dict[str, Any] = field(default_factory=dict)
    input_value: str = ""


CardActionHandler = Callable[[FeishuCardActionEvent], Mapping[str, Any] | None]


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
        worker_incarnation: str | None = None,
        status_callback: Callable[[FeishuWorkerStatus], None] | None = None,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._domain = domain
        self._worker_incarnation = worker_incarnation or f"feishu-{time.time_ns()}"
        self._status_callback = status_callback or self._log_worker_status
        self._on_message: Callable[[FeishuMessageEvent], None] | None = None
        self._on_card_action: CardActionHandler | None = None
        self._rest_client: lark.Client | None = None
        self._worker: FeishuWorkerRuntime | None = None
        self._last_stop_report: FeishuWorkerStopReport | None = None
        self._diagnostics = summarize_diagnostics(evaluate_scope_capabilities(None))

    def start(
        self,
        on_message: Callable[[FeishuMessageEvent], None],
        *,
        on_card_action: CardActionHandler | None = None,
    ) -> None:
        """Start REST in the parent and WebSocket in an isolated child process.

        Args:
            on_message: Callback invoked for each received message event.
            on_card_action: Optional callback invoked for interactive-card actions.
        """
        self._on_message = on_message
        self._on_card_action = on_card_action

        self._rest_client = (
            lark.Client.builder()
            .app_id(self._app_id)
            .app_secret(self._app_secret)
            .domain(self._domain)
            .build()
        )
        self._diagnostics = self.probe_capabilities()
        self._worker = FeishuWorkerRuntime(
            app_id=self._app_id,
            app_secret=self._app_secret,
            domain=self._domain,
            incarnation=self._worker_incarnation,
            on_event=on_message,
            on_status=self._forward_worker_status,
            on_card_action=on_card_action,
        )
        self._worker.start()
        logger.info("feishu ws client started for app %s", self._app_id[:8])

    def stop(self, *, drain: bool = True) -> None:
        """Stop, join, and if necessary terminate the isolated listener process."""
        self._on_message = None
        self._on_card_action = None
        if self._worker is not None:
            self._last_stop_report = self._worker.stop(drain=drain)
            self._worker = None
        self._rest_client = None
        logger.info("feishu ws client stopped for app %s", self._app_id[:8])

    @property
    def last_stop_report(self) -> FeishuWorkerStopReport | None:
        """Expose the last child cleanup result for lifecycle diagnostics."""
        return self._last_stop_report

    @staticmethod
    def _log_worker_status(status: FeishuWorkerStatus) -> None:
        logger.info(
            "feishu worker status: state=%s code=%s incarnation=%s seq=%s",
            status.connection_state,
            status.status_code,
            status.runtime_incarnation,
            status.status_sequence,
        )

    def probe_tenant_scope_grants(self) -> FeishuScopeProbe:
        """Read one complete application-v6 tenant authorization snapshot."""
        if self._rest_client is None:
            raise RuntimeError("feishu client is not started")
        try:
            response = self._rest_client.application.v6.scope.list(
                ListScopeRequest.builder().build()
            )
        except Exception:  # noqa: BLE001 - SDK transport failures are unknown probes.
            logger.warning("failed to list feishu app scopes", exc_info=True)
            return FeishuScopeProbe(False, None, "scope_api_failed")
        if not response.success():
            logger.warning(
                "failed to list feishu app scopes: code=%s, msg=%s",
                response.code,
                response.msg,
            )
            return FeishuScopeProbe(False, None, "scope_api_failed")
        return normalize_tenant_scope_grants(getattr(response, "data", None))

    def probe_capabilities(self) -> FeishuDiagnostics:
        """Evaluate every Feishu runtime capability from one tenant probe."""
        probe = self.probe_tenant_scope_grants()
        return summarize_diagnostics(evaluate_scope_capabilities(probe.granted_scopes))

    def _forward_worker_status(self, status: FeishuWorkerStatus) -> None:
        """Attach the immutable capability snapshot to every connection state."""
        self._status_callback(
            replace(
                status,
                diagnostics_state=self._diagnostics.state,
                checks=self._diagnostics.check_payloads(),
            )
        )

    def send_message(
        self,
        *,
        receive_id: str,
        text: str,
        receive_id_type: str = "chat_id",
    ) -> None:
        """Send Markdown text as a Feishu rich-text post.

        Error handling strategy:
        - 429 (rate limit): exponential backoff retry, max 3 attempts
        - 401/403 (auth): raise FeishuAuthError immediately, no retry
        - 5xx (server): retry once
        - Other errors: raise FeishuAPIError immediately

        Args:
            receive_id: Target chat or user identifier.
            text: Markdown message content.
            receive_id_type: Type of receive_id (``chat_id``, ``open_id``, etc.).

        Raises:
            RuntimeError: When the client has not been started.
            FeishuAuthError: When the feishu API returns 401/403.
            FeishuAPIError: When the feishu API returns any other error.
        """
        resolved_text = self._resolve_outbound_markdown_images(text)
        content = json.dumps(
            {
                "zh_cn": {
                    "content": [[{"tag": "md", "text": resolved_text}]],
                }
            },
            ensure_ascii=False,
        )
        self._send_create_message(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            msg_type="post",
            content=content,
        )

    def download_message_image(
        self,
        *,
        message_id: str,
        image_key: str,
    ) -> FeishuImageResource:
        """Download one standalone or post-embedded image from a message."""
        if self._rest_client is None:
            raise RuntimeError("feishu client is not started")
        request = (
            GetMessageResourceRequest.builder()
            .message_id(message_id)
            .file_key(image_key)
            .type("image")
            .build()
        )
        response = self._rest_client.im.v1.message_resource.get(request)
        if not response.success():
            _raise_api_error(response, action="downloading message image")

        stream = getattr(response, "file", None)
        data = (
            stream.read(_MAX_INBOUND_IMAGE_BYTES + 1)
            if hasattr(stream, "read")
            else stream
        )
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise FeishuAPIError(
                "feishu returned an empty message image",
                code=0,
            )
        if len(data) > _MAX_INBOUND_IMAGE_BYTES:
            raise FeishuImageTooLargeError(
                "feishu message image exceeds the 5 MiB inbound limit",
                code=0,
            )
        content_type = _response_content_type(response) or _detect_image_content_type(
            bytes(data)
        )
        file_name = getattr(response, "file_name", None)
        return FeishuImageResource(
            data=bytes(data),
            content_type=content_type or "image/jpeg",
            file_name=(
                str(file_name).strip()
                if isinstance(file_name, str) and file_name.strip()
                else None
            ),
        )

    def _resolve_outbound_markdown_images(self, text: str) -> str:
        """Upload Markdown image sources and replace them with Feishu image keys."""

        sources: list[str] = []

        def collect_image(match: re.Match[str]) -> str:
            source = match.group(2)
            if not source.startswith("img_") and source not in sources:
                if len(sources) >= _MAX_OUTBOUND_IMAGE_SOURCES:
                    raise ValueError(
                        "one Feishu message supports at most five uploaded image sources"
                    )
                sources.append(source)
            return match.group(0)

        _replace_markdown_images_outside_code(text, collect_image)
        resolved: dict[str, tuple[bytes, str]] = {}
        if sources:
            with ThreadPoolExecutor(max_workers=len(sources)) as executor:
                downloads = {
                    source: executor.submit(_read_outbound_image, source)
                    for source in sources
                }
                resolved = {source: downloads[source].result() for source in sources}
        uploaded = {
            source: self._upload_image(data, content_type=content_type)
            for source, (data, content_type) in resolved.items()
        }

        def replace_image(match: re.Match[str]) -> str:
            image_key = uploaded.get(match.group(2))
            if image_key is None:
                return match.group(0)
            return f"![{match.group(1)}]({image_key})"

        return _replace_markdown_images_outside_code(text, replace_image)

    def _upload_image(self, data: bytes, *, content_type: str) -> str:
        if self._rest_client is None:
            raise RuntimeError("feishu client is not started")
        stream = io.BytesIO(data)
        stream.name = f"image.{_image_extension(content_type)}"
        body = (
            CreateImageRequestBody.builder().image_type("message").image(stream).build()
        )
        request = CreateImageRequest.builder().request_body(body).build()
        response = self._rest_client.im.v1.image.create(request)
        if not response.success():
            _raise_api_error(response, action="uploading message image")
        image_key = str(getattr(getattr(response, "data", None), "image_key", ""))
        if not image_key:
            raise FeishuAPIError("feishu image upload returned no image_key", code=0)
        return image_key

    def send_interactive_message(
        self,
        *,
        receive_id: str,
        card: Mapping[str, Any],
        receive_id_type: str = "chat_id",
    ) -> str | None:
        """Send a Feishu interactive card and return its message id if present."""
        content = json.dumps(dict(card), ensure_ascii=False)
        return self._send_create_message(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            msg_type="interactive",
            content=content,
        )

    def update_interactive_message(
        self,
        *,
        message_id: str,
        card: Mapping[str, Any],
    ) -> None:
        """Replace an existing Feishu message with an updated interactive card."""
        if self._rest_client is None:
            raise RuntimeError("feishu client is not started")
        if not message_id:
            return

        body = (
            UpdateMessageRequestBody.builder()
            .msg_type("interactive")
            .content(json.dumps(dict(card), ensure_ascii=False))
            .build()
        )
        request = (
            UpdateMessageRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )

        response = self._rest_client.im.v1.message.update(request)
        if response.success():
            return
        _raise_api_error(response, action="updating interactive message")

    def _send_create_message(
        self,
        *,
        receive_id: str,
        receive_id_type: str,
        msg_type: str,
        content: str,
    ) -> str | None:
        """Create a Feishu message with the shared retry/error policy."""
        if self._rest_client is None:
            raise RuntimeError("feishu client is not started")
        cleaned_receive_id = receive_id.strip()
        if not cleaned_receive_id:
            raise ValueError("feishu receive_id must be non-empty")

        body = (
            CreateMessageRequestBody.builder()
            .receive_id(cleaned_receive_id)
            .msg_type(msg_type)
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

        while True:
            response = self._rest_client.im.v1.message.create(request)
            if response.success():
                data = getattr(response, "data", None)
                message_id = getattr(data, "message_id", None)
                return str(message_id) if message_id else None

            code: int = response.code
            msg: str = response.msg

            if code in _AUTH_ERROR_CODES:
                raise FeishuAuthError(
                    f"feishu auth error: code={code}, msg={msg}",
                    code=code,
                )

            if code in _RATE_LIMIT_CODES:
                rate_limit_attempt += 1
                if rate_limit_attempt >= max_rate_limit_attempts:
                    raise FeishuAPIError(
                        f"feishu rate limit exceeded after {max_rate_limit_attempts} "
                        f"attempts: code={code}, msg={msg}",
                        code=code,
                    )
                backoff = _BACKOFF_BASE_SECONDS * (2 ** (rate_limit_attempt - 1))
                logger.warning(
                    "feishu rate limited (code=%d), retrying in %.1fs (attempt %d/%d)",
                    code,
                    backoff,
                    rate_limit_attempt,
                    max_rate_limit_attempts,
                )
                time.sleep(backoff)
                continue

            if code in _SERVER_ERROR_CODES:
                server_error_attempt += 1
                if server_error_attempt >= max_server_error_attempts:
                    raise FeishuAPIError(
                        f"feishu server error after {max_server_error_attempts} "
                        f"attempts: code={code}, msg={msg}",
                        code=code,
                    )
                logger.warning(
                    "feishu server error (code=%d), retrying once",
                    code,
                )
                time.sleep(_BACKOFF_BASE_SECONDS)
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
            .sort_type("ByCreateTimeDesc")
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
        events: list[FeishuMessageEvent] = []
        for item in reversed(items):
            if _message_type(item) not in {"text", "post", "image"}:
                continue
            event = _parse_feishu_history_message(item, chat_id=chat_id)
            if event.text.strip() or event.image_keys:
                events.append(event)
        return events

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

    def _handle_card_action_event(self, event: Any) -> P2CardActionTriggerResponse:
        """Internal callback registered for Feishu interactive-card actions."""
        card: Mapping[str, Any] | None = None
        try:
            parsed = _parse_feishu_card_action_event(event)
            if self._on_card_action is not None:
                card = self._on_card_action(parsed)
        except Exception:
            logger.exception("failed to handle feishu card action event")
        return _card_action_response(card)

    def _ignore_reaction_event(self, _event: Any) -> None:
        """Accept reaction events generated by ack reactions without side effects."""
        return None


def _run_feishu_sdk_worker(context: FeishuWorkerProcessContext) -> None:
    """Own one lark-oapi event loop and listener entirely inside its child process."""

    def on_message(event: Any) -> None:
        try:
            publish_event(context, _parse_feishu_event(event))
        except Exception:
            logger.exception("failed to parse Feishu worker message")

    def on_card_action(event: Any) -> P2CardActionTriggerResponse:
        try:
            parsed = _parse_feishu_card_action_event(event)
            response = request_card_action(context, parsed)
        except Exception:
            logger.exception("failed to proxy Feishu card action")
            response = None
        return _card_action_response(response)

    builder = EventDispatcherHandler.builder("", "")
    builder.register_p2_im_message_receive_v1(on_message)
    builder.register_p2_im_message_reaction_created_v1(lambda _event: None)
    builder.register_p2_im_message_reaction_deleted_v1(lambda _event: None)
    builder.register_p2_card_action_trigger(on_card_action)
    client = WSClient(
        app_id=context.app_id,
        app_secret=context.app_secret,
        # lark-oapi INFO logs include the complete WebSocket URL, whose query
        # carries short-lived access_key and ticket credentials.
        log_level=LogLevel.WARNING,
        event_handler=builder.build(),
        domain=context.domain,
        auto_reconnect=True,
    )
    original_connect = client._connect

    async def observed_connect() -> None:
        await original_connect()
        publish_priority_status(context, connection_state="connected")

    client._connect = observed_connect
    client.on_reconnecting = lambda: publish_status(
        context, connection_state="reconnecting"
    )
    client.on_reconnected = lambda: publish_priority_status(
        context, connection_state="connected"
    )
    publish_status(context, connection_state="connecting")
    client.start()


def _raise_api_error(response: Any, *, action: str) -> None:
    code: int = response.code
    msg: str = response.msg
    if code in _AUTH_ERROR_CODES:
        raise FeishuAuthError(
            f"feishu auth error while {action}: code={code}, msg={msg}",
            code=code,
        )
    raise FeishuAPIError(
        f"feishu API error while {action}: code={code}, msg={msg}",
        code=code,
    )


def _response_content_type(response: Any) -> str | None:
    raw = getattr(response, "raw", None)
    headers = getattr(raw, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    value = headers.get("Content-Type") or headers.get("content-type")
    if not isinstance(value, str):
        return None
    normalized = value.split(";", 1)[0].strip().lower()
    return normalized if normalized.startswith("image/") else None


def _replace_markdown_images_outside_code(
    text: str,
    replacer: Callable[[re.Match[str]], str],
) -> str:
    """Replace image syntax while preserving escaped and code examples."""

    output: list[str] = []
    index = 0
    code_delimiter = 0
    while index < len(text):
        if text[index] == "`":
            end = index + 1
            while end < len(text) and text[end] == "`":
                end += 1
            run_length = end - index
            if code_delimiter == 0:
                code_delimiter = run_length
            elif code_delimiter == run_length:
                code_delimiter = 0
            output.append(text[index:end])
            index = end
            continue
        if code_delimiter == 0 and text.startswith("![", index):
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and text[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                match = _MARKDOWN_IMAGE_RE.match(text, index)
                if match is not None:
                    output.append(replacer(match))
                    index = match.end()
                    continue
        output.append(text[index])
        index += 1
    return "".join(output)


def _read_outbound_image(source: str) -> tuple[bytes, str]:
    if source.startswith("data:image/"):
        return _decode_image_data_url(source)

    parsed = urlsplit(source)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("feishu Markdown images require a public HTTP(S) or data URL")
    if parsed.username or parsed.password:
        raise ValueError("feishu Markdown image URLs must not contain credentials")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = _resolve_public_addresses(parsed.hostname, port)
    data = _download_from_pinned_public_address(parsed, addresses, port=port)
    content_type = _detect_image_content_type(data)
    if content_type is None:
        raise ValueError("feishu outbound image is not a supported raster image")
    return data, content_type


def _decode_image_data_url(source: str) -> tuple[bytes, str]:
    header, separator, encoded = source.partition(",")
    if not separator or ";base64" not in header.lower():
        raise ValueError("feishu image data URLs must use base64 encoding")
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError("feishu image data URL contains invalid base64") from exc
    if len(data) > _MAX_OUTBOUND_IMAGE_BYTES:
        raise ValueError("feishu outbound image exceeds 10 MB")
    content_type = _detect_image_content_type(data)
    if content_type is None:
        raise ValueError("feishu outbound image is not a supported raster image")
    return data, content_type


def _resolve_public_addresses(host: str, port: int) -> tuple[str, ...]:
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("feishu Markdown image host could not be resolved") from exc
    public_addresses: list[str] = []
    for address in addresses:
        raw_ip = address[4][0]
        ip = ipaddress.ip_address(raw_ip)
        if not ip.is_global:
            raise ValueError("feishu Markdown image URL must resolve to a public host")
        if raw_ip not in public_addresses:
            public_addresses.append(raw_ip)
    if not public_addresses:
        raise ValueError("feishu Markdown image host could not be resolved")
    return tuple(public_addresses)


def _download_from_pinned_public_address(
    parsed: SplitResult,
    addresses: tuple[str, ...],
    *,
    port: int,
) -> bytes:
    """Download through a validated IP while preserving HTTP Host and TLS SNI."""

    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    last_error: Exception | None = None
    deadline = time.monotonic() + 15.0
    for address in addresses:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        connection_type = (
            http.client.HTTPSConnection
            if parsed.scheme == "https"
            else http.client.HTTPConnection
        )
        connection = connection_type(parsed.hostname, port=port, timeout=remaining)

        def create_pinned_connection(
            _address: tuple[str, int],
            timeout: float | object = socket._GLOBAL_DEFAULT_TIMEOUT,
            source_address: tuple[str, int] | None = None,
            *,
            all_errors: bool = False,
        ) -> socket.socket:
            return socket.create_connection(
                (address, port),
                timeout,
                source_address,
                all_errors=all_errors,
            )

        # HTTPConnection uses this hook before HTTPS wraps the socket with the
        # original hostname, so the validated address is pinned without losing SNI.
        connection._create_connection = create_pinned_connection  # type: ignore[attr-defined]
        try:
            connection.request(
                "GET",
                target,
                headers={"User-Agent": "nano-multiagent/1.0"},
            )
            response = connection.getresponse()
            if response.status >= 400:
                raise ValueError(
                    f"feishu outbound image request failed with HTTP {response.status}"
                )
            chunks: list[bytes] = []
            size = 0
            while chunk := response.read(64 * 1024):
                size += len(chunk)
                if size > _MAX_OUTBOUND_IMAGE_BYTES:
                    raise ValueError("feishu outbound image exceeds 10 MB")
                chunks.append(chunk)
            return b"".join(chunks)
        except (OSError, http.client.HTTPException) as exc:
            last_error = exc
        finally:
            connection.close()
    raise ValueError("feishu outbound image could not be downloaded") from last_error


def _detect_image_content_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _image_extension(content_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
    }.get(content_type, "png")


def _parse_feishu_card_action_event(event: Any) -> FeishuCardActionEvent:
    raw_event = getattr(event, "event", None)
    action = getattr(raw_event, "action", None)
    operator = getattr(raw_event, "operator", None)
    context = getattr(raw_event, "context", None)
    value = getattr(action, "value", None)
    if not isinstance(value, dict):
        value = {}
    form_value = getattr(action, "form_value", None)
    if not isinstance(form_value, dict):
        form_value = {}
    return FeishuCardActionEvent(
        action_value=dict(value),
        operator_open_id=str(getattr(operator, "open_id", "") or ""),
        operator_user_id=str(getattr(operator, "user_id", "") or ""),
        open_chat_id=str(getattr(context, "open_chat_id", "") or ""),
        form_value=dict(form_value),
        input_value=str(getattr(action, "input_value", "") or ""),
    )


def _card_action_response(
    card: Mapping[str, Any] | None,
) -> P2CardActionTriggerResponse:
    if not card:
        return P2CardActionTriggerResponse()
    return P2CardActionTriggerResponse({"card": {"type": "raw", "data": dict(card)}})


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

    mentions = _extract_mentions(message)
    message_type = _message_type(message)
    raw_parts = _extract_message_content_parts(
        message_type=message_type,
        raw_content=raw_content,
        mentions=mentions,
    )
    content_parts = _normalize_content_parts(raw_parts, mentions)
    include_image_markers = message_type.strip().lower() == "post"
    raw_text = _project_content_parts(
        raw_parts,
        include_image_markers=include_image_markers,
    )
    text = _project_content_parts(
        content_parts,
        include_image_markers=include_image_markers,
    )
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
        image_keys=_content_image_keys(content_parts),
        content_parts=content_parts,
    )


def _parse_feishu_history_message(message: Any, *, chat_id: str) -> FeishuMessageEvent:
    sender_open_id = _extract_message_sender_open_id(message)
    message_id = str(getattr(message, "message_id", "") or getattr(message, "id", ""))
    raw_content = _extract_message_content(message)
    mentions = _extract_mentions(message)
    message_type = _message_type(message)
    raw_parts = _extract_message_content_parts(
        message_type=message_type,
        raw_content=raw_content,
        mentions=mentions,
    )
    content_parts = _normalize_content_parts(raw_parts, mentions)
    include_image_markers = message_type.strip().lower() == "post"
    raw_text = _project_content_parts(
        raw_parts,
        include_image_markers=include_image_markers,
    )
    text = _project_content_parts(
        content_parts,
        include_image_markers=include_image_markers,
    )
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
        image_keys=_content_image_keys(content_parts),
        content_parts=content_parts,
    )


def _message_type(message: Any) -> str:
    for attr in ("message_type", "msg_type"):
        value = getattr(message, attr, "")
        if isinstance(value, str) and value:
            return value
    return ""


def _extract_message_content(message: Any) -> str:
    for value in (
        getattr(message, "content", None),
        getattr(getattr(message, "body", None), "content", None),
    ):
        if isinstance(value, str) and value:
            return value
    if isinstance(message, dict):
        for key in ("content", "body"):
            value = message.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict):
                nested = value.get("content")
                if isinstance(nested, str) and nested:
                    return nested
    return ""


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
    for attr in ("sender_name", "name", "tenant_key"):
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


def _extract_message_content_parts(
    *,
    message_type: str,
    raw_content: str,
    mentions: list[FeishuMention],
) -> tuple[FeishuContentPart, ...]:
    """Parse one provider payload without collapsing text/image order."""

    normalized_type = message_type.strip().lower()
    if normalized_type == "post":
        return _extract_post_content_parts(raw_content, mentions=mentions)
    if normalized_type == "image":
        key = _extract_standalone_image_key(raw_content)
        return (FeishuContentPart(kind="image", image_key=key),) if key else ()
    text = _extract_text(raw_content)
    return (FeishuContentPart(kind="text", text=text),) if text else ()


def _extract_standalone_image_key(raw_content: str) -> str:
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(parsed, dict):
        return ""
    return str(parsed.get("image_key", "") or "").strip()


def _extract_post_content_parts(
    raw_content: str,
    *,
    mentions: list[FeishuMention],
) -> tuple[FeishuContentPart, ...]:
    """Render a Feishu post into ordered Markdown text and image nodes."""

    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return (FeishuContentPart(kind="text", text="[富文本消息]"),)

    payload = _resolve_post_payload(parsed)
    if payload is None:
        return (FeishuContentPart(kind="text", text="[富文本消息]"),)

    parts: list[FeishuContentPart] = []
    title = payload["title"].strip()
    if title:
        _append_content_text(parts, title)
        if payload["content"]:
            _append_content_text(parts, "\n\n")
    for paragraph_index, paragraph in enumerate(payload["content"]):
        if not isinstance(paragraph, list):
            continue
        if paragraph_index:
            _append_content_text(parts, "\n")
        for element in paragraph:
            if isinstance(element, dict) and str(
                element.get("tag", "")
            ).strip().lower() in {"img", "image"}:
                image_key = str(element.get("image_key", "") or "").strip()
                if image_key:
                    parts.append(FeishuContentPart(kind="image", image_key=image_key))
                continue
            _append_content_text(
                parts,
                _render_post_element(element, mentions=mentions),
            )
    if not parts:
        return (FeishuContentPart(kind="text", text="[富文本消息]"),)
    return tuple(parts)


def _append_content_text(parts: list[FeishuContentPart], text: str) -> None:
    if not text:
        return
    if parts and parts[-1].kind == "text":
        previous = parts[-1]
        parts[-1] = FeishuContentPart(kind="text", text=previous.text + text)
        return
    parts.append(FeishuContentPart(kind="text", text=text))


def _normalize_content_parts(
    parts: tuple[FeishuContentPart, ...],
    mentions: list[FeishuMention],
) -> tuple[FeishuContentPart, ...]:
    return tuple(
        FeishuContentPart(
            kind="text",
            text=_replace_mention_placeholders(part.text, mentions),
        )
        if part.kind == "text"
        else part
        for part in parts
    )


def _project_content_parts(
    parts: tuple[FeishuContentPart, ...],
    *,
    include_image_markers: bool,
) -> str:
    return "".join(
        part.text if part.kind == "text" else "[图片]" if include_image_markers else ""
        for part in parts
    ).strip("\n")


def _content_image_keys(
    parts: tuple[FeishuContentPart, ...],
) -> tuple[str, ...]:
    keys: list[str] = []
    for part in parts:
        if part.kind == "image" and part.image_key and part.image_key not in keys:
            keys.append(part.image_key)
    return tuple(keys)


def _resolve_post_payload(parsed: Any) -> dict[str, Any] | None:
    direct = _as_post_payload(parsed)
    if direct is not None:
        return direct
    if not isinstance(parsed, dict):
        return None

    wrapped = parsed.get("post")
    direct = _resolve_localized_post(wrapped)
    if direct is not None:
        return direct
    return _resolve_localized_post(parsed)


def _resolve_localized_post(candidate: Any) -> dict[str, Any] | None:
    direct = _as_post_payload(candidate)
    if direct is not None:
        return direct
    if not isinstance(candidate, dict):
        return None
    for value in candidate.values():
        direct = _as_post_payload(value)
        if direct is not None:
            return direct
    return None


def _as_post_payload(candidate: Any) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None
    content = candidate.get("content_v2")
    if not isinstance(content, list):
        content = candidate.get("content")
    if not isinstance(content, list):
        return None
    return {
        "title": str(candidate.get("title", "") or ""),
        "content": content,
    }


def _render_post_element(
    element: Any,
    *,
    mentions: list[FeishuMention],
) -> str:
    if isinstance(element, str):
        return element
    if not isinstance(element, dict):
        return ""

    tag = str(element.get("tag", "")).strip().lower()
    if tag == "text":
        return _render_styled_post_text(element)
    if tag in {"md", "lark_md"}:
        return str(element.get("text", "") or element.get("content", "") or "")
    if tag == "a":
        href = str(element.get("href", "") or "").strip()
        label = str(element.get("text", "") or href)
        return f"[{label}]({href})" if href else label
    if tag == "at":
        return _render_post_mention(element, mentions=mentions)
    if tag in {"img", "image"}:
        return ""
    if tag in {"media", "file", "audio", "video"}:
        file_name = str(element.get("file_name", "") or "").strip()
        return f"[附件: {file_name}]" if file_name else "[附件]"
    if tag in {"emotion", "emoji"}:
        return str(element.get("text", "") or element.get("emoji_type", "") or "")
    if tag == "br":
        return "\n"
    if tag in {"hr", "divider"}:
        return "\n\n---\n\n"
    if tag == "code":
        return wrap_inline_code(
            str(element.get("text", "") or element.get("content", "") or "")
        )
    if tag in {"code_block", "pre"}:
        language = str(element.get("language", "") or element.get("lang", "") or "")
        code = str(element.get("text", "") or element.get("content", "") or "")
        return f"```{language}\n{code}\n```"
    return str(element.get("text", "") or "")


def _render_styled_post_text(element: dict[str, Any]) -> str:
    text = str(element.get("text", "") or "")
    style = element.get("style")
    if _post_style_enabled(style, "code"):
        return wrap_inline_code(text)
    if _post_style_enabled(style, "bold"):
        text = f"**{text}**"
    if _post_style_enabled(style, "italic"):
        text = f"*{text}*"
    if _post_style_enabled(style, "underline"):
        text = f"<u>{text}</u>"
    if any(
        _post_style_enabled(style, name)
        for name in ("strikethrough", "line_through", "lineThrough")
    ):
        text = f"~~{text}~~"
    return text


def _post_style_enabled(style: Any, name: str) -> bool:
    if isinstance(style, list):
        return name in style
    if isinstance(style, dict):
        return bool(style.get(name))
    return False


def wrap_inline_code(text: str) -> str:
    """Wrap arbitrary text in a collision-free Markdown inline-code fence."""
    longest_run = 0
    current_run = 0
    for char in text:
        if char == "`":
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 0
    fence = "`" * (longest_run + 1)
    padded = f" {text} " if text.startswith("`") or text.endswith("`") else text
    return f"{fence}{padded}{fence}"


def _render_post_mention(
    element: dict[str, Any],
    *,
    mentions: list[FeishuMention],
) -> str:
    mention_id = str(
        element.get("user_id", "") or element.get("open_id", "") or ""
    ).strip()
    if mention_id == _ALL_MENTION_PLACEHOLDER:
        return _ALL_MENTION_PLACEHOLDER
    for mention in mentions:
        if mention_id in {mention.key, mention.open_id}:
            return mention.key or _visible_mention_text(mention)
    name = str(element.get("user_name", "") or mention_id).strip()
    return f"@{name}" if name and not name.startswith("@") else name


def _normalize_mention_text(text: str, mentions: list[FeishuMention]) -> str:
    """Replace Feishu mention placeholders with user-visible @ labels."""

    return _collapse_spaces(_replace_mention_placeholders(text, mentions))


def _replace_mention_placeholders(text: str, mentions: list[FeishuMention]) -> str:
    """Replace mention placeholders without changing surrounding whitespace."""

    normalized = text.replace(_ALL_MENTION_PLACEHOLDER, "@所有人")
    for mention in mentions:
        if not mention.key:
            continue
        normalized = normalized.replace(mention.key, _visible_mention_text(mention))
    return normalized


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
        mention_id = getattr(m, "id", "")
        if isinstance(mention_id, str):
            open_id = mention_id.strip()
        else:
            value = getattr(mention_id, "open_id", "")
            open_id = value.strip() if isinstance(value, str) else ""
        name = getattr(m, "name", "") or ""
        key = getattr(m, "key", "") or ""
        if open_id:
            result.append(FeishuMention(open_id=open_id, name=name, key=key))
    return result


def _read_value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
