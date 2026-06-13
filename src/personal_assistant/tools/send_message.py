"""Product-owned send_message tool for personal_assistant agent collaboration.

Stateless design: the tool reads the Gateway dispatch endpoint URL from
``ctx.session_metadata["gateway_dispatch_url"]`` at execution time and sends
the message via an HTTP POST.  No module-level singleton, no bind_dispatcher.
"""

from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

import httpx

from agent.sdk import ToolContext


class SendMessageTool:
    """Send an IM-routed message to another agent or shared group.

    The tool is stateless: it derives the dispatch endpoint from the kernel
    session metadata key ``gateway_dispatch_url`` injected by the Gateway
    inbound pipeline when creating the session.  The Gateway must expose a
    ``POST /internal/dispatch`` endpoint that accepts the forwarded payload.

    Raises:
        RuntimeError: When ``gateway_dispatch_url`` is absent from session metadata.
        ValueError: When ``text`` or ``to`` arguments are blank.
    """

    name = "send_message"
    description = (
        "Send a message via the gateway IM routing layer. "
        "`to` accepts stable business ids: user_id, agent_id, or conversation_id."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Message body to send."},
            "to": {
                "type": "string",
                "description": "Target stable id: user_id, agent_id, or conversation_id.",
            },
        },
        "required": ["text", "to"],
        "additionalProperties": False,
    }

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Dispatch one collaboration message through the gateway HTTP boundary.

        Args:
            args: Tool arguments; must contain ``text`` and ``to``.
            ctx: Execution context; ``ctx.session_metadata`` must carry
                ``gateway_dispatch_url`` pointing to the Gateway internal endpoint.

        Returns:
            Dict with ``ok``, ``target``, and ``text`` fields on success.

        Raises:
            RuntimeError: When ``gateway_dispatch_url`` is not configured in
                session metadata.  Configure it by setting ``gateway_internal_port``
                on InboundPipeline or by manually injecting the key into session
                metadata.
            ValueError: When ``text`` or ``to`` arguments are blank.
        """

        dispatch_url = ctx.session_metadata.get("gateway_dispatch_url")
        if not isinstance(dispatch_url, str) or not dispatch_url.strip():
            raise RuntimeError(
                "send_message: gateway_dispatch_url is not configured in session metadata. "
                "Ensure the Gateway inbound pipeline injects gateway_dispatch_url when creating the session."
            )

        text = _require_text(args.get("text"), field_name="text")
        target = _require_text(args.get("to"), field_name="to")

        source_agent_id = ctx.session_metadata.get("agent_id")
        if isinstance(source_agent_id, str) and source_agent_id.strip():
            dispatch_source = source_agent_id.strip()
        else:
            dispatch_source = ctx.session_id

        dispatch_request_id: str | None = None
        if isinstance(ctx.tool_call_id, str) and ctx.tool_call_id.strip():
            dispatch_request_id = ctx.tool_call_id.strip()
        else:
            dispatch_request_id = uuid4().hex
        if (
            isinstance(dispatch_source, str)
            and dispatch_source.strip()
            and dispatch_request_id
        ):
            dispatch_source = (
                f"{dispatch_source.strip()}|tool_call:{dispatch_request_id}"
            )

        payload: dict[str, Any] = {
            "text": text,
            "to": target,
            "from_session_id": dispatch_source,
            "origin_kernel_session_id": ctx.session_id,
            "source_agent_id": source_agent_id.strip()
            if isinstance(source_agent_id, str) and source_agent_id.strip()
            else None,
            "dispatch_request_id": dispatch_request_id,
        }
        timeout = httpx.Timeout(connect=3.0, write=10.0, read=None, pool=3.0)
        response = httpx.post(dispatch_url.strip(), json=payload, timeout=timeout)
        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "send_message: gateway dispatch returned non-JSON response"
            ) from exc
        if not isinstance(body, Mapping):
            raise RuntimeError(
                "send_message: gateway dispatch returned non-object response"
            )
        if response.status_code >= 400 or body.get("ok") is not True:
            error = body.get("error")
            if isinstance(error, str) and error.strip():
                raise RuntimeError(f"send_message: {error.strip()}")
            raise RuntimeError(
                f"send_message: gateway dispatch failed with status {response.status_code}"
            )

        return {
            "ok": True,
            "target": target,
            "text": text,
            "dispatch_request_id": dispatch_request_id,
        }


def get_tool() -> SendMessageTool:
    """Return a fresh stateless SendMessageTool instance for tool loader discovery."""
    return SendMessageTool()


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()
