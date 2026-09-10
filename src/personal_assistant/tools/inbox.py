"""Query the global Inbox through the Gateway's authenticated session boundary."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from agent.sdk import PermissionDecision, ToolContext, ToolPresentationEvent
from personal_assistant.tools.inbox_result import model_page


def content_digest(content: Any) -> str:
    """Hash model content using the SDK's durable-message canonical format."""
    from agent.sdk import tool_content_digest

    return tool_content_digest(content)


def serialize_page(output: Any, error: str | None = None) -> str | list[dict[str, Any]]:
    """Serialize the complete bounded page, including actual image blocks.

    Images are emitted as provider-neutral blocks; the JSON text retains their
    message identity and position without duplicating image data as JSON text.
    """
    if error is not None:
        return error
    images: list[dict[str, Any]] = []
    page = json.loads(json.dumps(output, ensure_ascii=False))
    if isinstance(page, dict):
        for message in page.get("messages", []):
            if "content" not in message:
                continue
            blocks = []
            for block in message.get("content", []):
                if block.get("type") == "image":
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        images.append(
                            {
                                "type": "image",
                                "data": source["data"],
                                "mimeType": source["media_type"],
                            }
                        )
                    else:
                        raise ValueError(
                            "attachment_unavailable: image has not been materialized"
                        )
                    blocks.append({"type": "image", "image_index": len(images) - 1})
                else:
                    blocks.append(block)
            message["content"] = blocks
    text = json.dumps(
        page, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return [{"type": "text", "text": text}, *images] if images else text


def serialize_inbox_page(
    output: Any, error: str | None = None
) -> str | list[dict[str, Any]]:
    """Serialize only model-facing fields; internal receipts stay in the Gateway."""
    return serialize_page(model_page(output), error) if error is None else error


def validate_arguments(tool_name: str, args: Mapping[str, Any]) -> None:
    """Reject invalid action fields before any Gateway operation."""
    action = args.get("action")
    allowed = {
        ("inbox", "check"): {"action", "cursor", "limit"},
        ("inbox", "read"): {"action", "target", "cursor", "limit"},
        ("conversations", "list"): {"action", "query", "cursor", "limit"},
        ("conversations", "info"): {"action", "target"},
        ("conversations", "read"): {
            "action",
            "target",
            "before_message_id",
            "cursor",
            "limit",
        },
    }.get((tool_name, action))
    if allowed is None or set(args) - allowed:
        raise ValueError("invalid_arguments: unsupported action or fields")
    limit = args.get("limit", 20)
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("invalid_arguments: limit must be 1–50")
    if action in {"read", "info"} and not args.get("target"):
        raise ValueError("invalid_arguments: target is required")
    for key in ("target", "cursor", "before_message_id", "query"):
        if key in args and (not isinstance(args[key], str) or not args[key].strip()):
            raise ValueError(f"invalid_arguments: {key} must be non-empty text")
    if args.get("before_message_id") and args.get("cursor"):
        raise ValueError(
            "invalid_arguments: before_message_id and cursor are mutually exclusive"
        )


class QueryPresenter:
    """Project real action parameters and results without reading or consuming."""

    def __init__(self, label: str) -> None:
        self.label = label

    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        """Expose parameters only while the query runs."""
        return ToolPresentationEvent(
            visible=True,
            label=self.label,
            summary=str(args.get("action", "")),
            detail=dict(args),
        )

    def format_end(
        self, args: Mapping[str, Any], result: Any, duration_ms: int
    ) -> ToolPresentationEvent:
        """Expose actual page results or errors while preserving query context."""
        detail = dict(args)
        error = getattr(result, "error", None)
        output = getattr(result, "output", None)
        if error:
            detail.update(status="failed", error=str(error))
        elif isinstance(output, Mapping):
            detail.update(output)
            detail["status"] = "completed"
        return ToolPresentationEvent(
            visible=True,
            label=self.label,
            summary=str(args.get("action", "")),
            detail=detail,
        )


class InboxTool:
    """Read bounded Inbox pages for the authenticated global main Session."""

    name = "inbox"
    description = (
        "Check which conversations have unread messages, or read them oldest first. "
        "Reading brings messages into your context and marks fully read messages as read; "
        "it does not complete a task or require a reply. partial marks an incomplete message; "
        "continue with next_cursor. Text, images and attachments stay in source order. Times are UTC."
    )
    presenter = QueryPresenter("Inbox")
    max_result_size_chars = None
    is_concurrency_safe = False
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["check", "read"],
                "description": "check: list conversations with unread messages; read: read unread content from one conversation.",
            },
            "target": {
                "type": "string",
                "description": "For read only, required: copy a conversation target (c_...) returned by check.",
            },
            "cursor": {
                "type": "string",
                "description": "Copy next_cursor from the previous result and keep the same action and target. Omit on the first page.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum conversations for check or message parts for read. A long message may span parts. Omit to check all conversations that fit in one page, or read up to 20 parts.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def __init__(
        self, *, gateway_dispatch_url_provider: Callable[[], str | None] | None = None
    ) -> None:
        self._provider = gateway_dispatch_url_provider

    def check_permissions(
        self, tool_input: Mapping[str, Any], ctx: ToolContext
    ) -> PermissionDecision:
        """Allow scoped queries; the Gateway checks identity and source access."""
        try:
            validate_arguments(self.name, tool_input)
        except ValueError as exc:
            return PermissionDecision(behavior="deny", reason=str(exc))
        return PermissionDecision(behavior="allow")

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Submit a session-scoped query to the live Gateway listener.

        Raises:
            ValueError: When action parameters are invalid.
            RuntimeError: When the listener or query is unavailable.
        """
        validate_arguments(self.name, args)
        url = (
            self._provider()
            if self._provider
            else ctx.session_metadata.get("gateway_dispatch_url")
        )
        if not isinstance(url, str) or not url.strip():
            raise RuntimeError("source_unavailable: Gateway listener is unavailable")
        parsed = urlsplit(url)
        endpoint = urlunsplit(
            (parsed.scheme, parsed.netloc, f"/internal/{self.name}", "", "")
        )
        response = httpx.post(
            endpoint,
            json={
                "source_agent_id": ctx.session_metadata.get("agent_id"),
                "origin_kernel_session_id": ctx.session_id,
                "tool_call_id": ctx.tool_call_id,
                "args": dict(args),
            },
            timeout=httpx.Timeout(connect=3, read=30, write=10, pool=3),
        )
        body = response.json()
        if (
            response.status_code >= 400
            or not isinstance(body, Mapping)
            or body.get("ok") is False
        ):
            error = (
                body.get("error", "source_unavailable")
                if isinstance(body, Mapping)
                else "source_unavailable"
            )
            raise RuntimeError(str(error))
        return body.get("result", body)

    def serialize_result(
        self, output: Any, error: str | None = None
    ) -> str | list[dict[str, Any]]:
        """Return the exact page used for the server's expected content digest."""
        return serialize_inbox_page(output, error)

    def to_auto_classifier_result(self, content: Any) -> str | None:
        """Expose received user requests to approval without promoting Agent replies.

        The main model receives these requests through a tool result rather than
        a native user turn. Retain their source identity for the same permission
        decision; ordinary query results and non-user messages grant no authority.
        """
        if isinstance(content, list):
            content = "\n".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        try:
            page = json.loads(content)
        except (ValueError, TypeError):
            return None
        if (
            self.name != "inbox"
            or not isinstance(page, dict)
            or not isinstance(page.get("messages"), list)
        ):
            return None
        requests = [
            {
                "message_id": message.get("id"),
                "sender": message.get("sender"),
                "target": page.get("target"),
                "partial": message.get("partial", False),
                "text": message.get("text")
                or "\n".join(
                    block.get("text", "")
                    for block in message.get("content", [])
                    if block.get("type") == "text"
                ),
            }
            for message in page.get("messages", [])
            if message.get("sender", {}).get("type") in {"user", "external"}
        ]
        return (
            "User messages received through this Agent's Inbox: "
            + json.dumps(requests, ensure_ascii=False)
            if requests
            else None
        )


def get_tool() -> InboxTool:
    """Return the standalone tool for product discovery."""
    return InboxTool()
