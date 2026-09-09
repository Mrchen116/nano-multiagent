"""Query the global Inbox through the Gateway's authenticated session boundary."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from agent.sdk import ToolContext, ToolPresentationEvent


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
            blocks = []
            for block in message.get("content", []):
                if block.get("type") == "image":
                    images.append(block)
                    blocks.append({"type": "image", "image_index": len(images) - 1})
                else:
                    blocks.append(block)
            message["content"] = blocks
    text = json.dumps(
        page, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return [{"type": "text", "text": text}, *images] if images else text


def validate_arguments(tool_name: str, args: Mapping[str, Any]) -> None:
    """Reject invalid action fields before any Gateway operation."""
    action = args.get("action")
    allowed = {
        ("inbox", "check"): {"action", "cursor", "limit"},
        ("inbox", "read"): {"action", "target", "cursor", "limit"},
        ("conversations", "list"): {"action", "query", "cursor", "limit"},
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
    if action == "read" and not args.get("target"):
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
    description = "Check pending conversation summaries or read their new messages. Reading is not task completion."
    presenter = QueryPresenter("Inbox")
    max_result_size_chars = None
    is_concurrency_safe = False
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["check", "read"]},
            "target": {"type": "string"},
            "cursor": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def __init__(
        self, *, gateway_dispatch_url_provider: Callable[[], str | None] | None = None
    ) -> None:
        self._provider = gateway_dispatch_url_provider

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
        return serialize_page(output, error)

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
        if not isinstance(page, dict) or not page.get("receipt_id"):
            return None
        requests = [
            {
                "message_id": message.get("message_id"),
                "sender": message["sender"],
                "source": message.get("source"),
                "complete_message": message.get("complete_message"),
                "text": "\n".join(
                    block.get("text", "")
                    for block in message.get("content", [])
                    if block.get("type") == "text"
                ),
            }
            for message in page.get("messages", [])
            if message.get("sender", {}).get("kind") == "user"
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
