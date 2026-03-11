"""Product-owned send_message tool for personal_assistant agent collaboration."""
from __future__ import annotations

from typing import Any, Mapping, Protocol

from agent.core.tools.base import ToolContext


class MessageDispatcher(Protocol):
    """Gateway-facing dispatch surface required by ``SendMessageTool``."""

    def send_message(self, *, text: str, to: str, session_id: str | None = None) -> Mapping[str, Any]:
        """Deliver one agent-to-agent message and return dispatch metadata."""


class SendMessageTool:
    """Send an IM-routed message to another agent or shared group.

    Args:
        dispatcher: Gateway-owned dispatcher that performs local or upstream routing.
    """

    name = "send_message"
    description = "Send a message to another agent or group via the gateway IM routing layer."
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Message body to send."},
            "to": {"type": "string", "description": "Target agent id or group id."},
        },
        "required": ["text", "to"],
        "additionalProperties": False,
    }

    def __init__(self, *, dispatcher: MessageDispatcher | None = None) -> None:
        self._dispatcher = dispatcher

    def bind_dispatcher(self, dispatcher: MessageDispatcher | None) -> None:
        """Bind the gateway dispatcher after bootstrap when needed."""

        self._dispatcher = dispatcher

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Dispatch one collaboration message through the gateway boundary."""

        dispatcher = self._dispatcher
        if dispatcher is None:
            raise RuntimeError("send_message dispatcher is not configured")
        text = _require_text(args.get("text"), field_name="text")
        target = _require_text(args.get("to"), field_name="to")
        result = dispatcher.send_message(text=text, to=target, session_id=ctx.session_id)
        return {
            "ok": True,
            "target": target,
            "text": text,
            "dispatch": dict(result),
        }


TOOL = SendMessageTool()


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()
