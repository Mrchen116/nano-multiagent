"""Internal Gateway HTTP dispatch endpoint for agent-to-agent message routing.

Exposes ``POST /internal/dispatch`` so that product tools (e.g. ``send_message``)
running inside the kernel can post outbound messages back through the Gateway's
existing IM routing layer without requiring a separate process or service.
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Mapping


class InternalDispatchHandler:
    """Handle ``POST /internal/dispatch`` requests from agent tools.

    The handler receives ``{text, to, from_session_id}`` and forwards the
    message to the IM layer using the live IM connection manager when available.

    Args:
        im_connection_manager: Optional live IM WebSocket manager.  When ``None``
            or disconnected, the handler returns an informative error rather than
            silently dropping the message.
    """

    def __init__(self, *, im_connection_manager: Any | None = None) -> None:
        self._im_connection_manager = im_connection_manager

    async def handle(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Process one dispatch request and return a response dict.

        Args:
            payload: Parsed request body; must contain ``text`` and ``to``.

        Returns:
            ``{"ok": True}`` on success or ``{"ok": False, "error": "..."}`` on failure.
        """

        text = payload.get("text")
        to = payload.get("to")
        from_session_id = payload.get("from_session_id")

        if not isinstance(text, str) or not text.strip():
            return {"ok": False, "error": "text must be a non-empty string"}
        if not isinstance(to, str) or not to.strip():
            return {"ok": False, "error": "to must be a non-empty string"}

        manager = self._im_connection_manager
        if manager is None:
            return {
                "ok": False,
                "error": "Gateway IM connection manager is not available; cannot dispatch message",
            }
        if not getattr(manager, "connected", False):
            return {
                "ok": False,
                "error": "Gateway IM connection is not active; cannot dispatch message",
            }

        dispatch_payload: dict[str, Any] = {
            "to": to.strip(),
            "text": text.strip(),
        }
        if isinstance(from_session_id, str) and from_session_id.strip():
            dispatch_payload["from_session_id"] = from_session_id.strip()

        try:
            await manager.send_json("agent.message", dispatch_payload)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"IM dispatch failed: {exc}"}

        return {"ok": True, "to": to.strip(), "text": text.strip()}

    def build_aiohttp_handler(self) -> Callable:
        """Return an aiohttp request handler for ``POST /internal/dispatch``.

        Returns:
            Async callable compatible with aiohttp route registration.
        """

        from aiohttp.web import Request, Response

        async def _handle(request: Request) -> Response:
            try:
                body = await request.json()
            except Exception:  # noqa: BLE001
                return Response(
                    status=400,
                    content_type="application/json",
                    text=json.dumps({"ok": False, "error": "invalid JSON body"}),
                )
            result = await self.handle(body)
            status = 200 if result.get("ok") else 503
            return Response(
                status=status,
                content_type="application/json",
                text=json.dumps(result),
            )

        return _handle
