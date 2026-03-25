"""Internal Gateway HTTP dispatch endpoint for agent-to-agent message routing.

Exposes ``POST /internal/dispatch`` so that product tools (e.g. ``send_message``)
running inside the kernel can post outbound messages back through the Gateway's
existing IM routing layer without requiring a separate process or service.
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Mapping

from personal_assistant.gateway.session_keys import bind_conversation_session


class InternalDispatchHandler:
    """Handle ``POST /internal/dispatch`` requests from agent tools.

    The handler receives ``{text, to, from_session_id}`` and forwards the
    message to the IM layer using the live IM connection manager when available.

    Args:
        im_connection_manager: Optional live IM WebSocket manager.  When ``None``
            or disconnected, the handler returns an informative error rather than
            silently dropping the message.
    """

    def __init__(
        self,
        *,
        im_connection_manager: Any | None = None,
        kernel_client: Any | None = None,
        session_store: Any | None = None,
        direct_channel_name: str = "web_relay",
    ) -> None:
        self._im_connection_manager = im_connection_manager
        self._kernel_client = kernel_client
        self._session_store = session_store
        self._direct_channel_name = direct_channel_name

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
        origin_kernel_session_id = payload.get("origin_kernel_session_id")
        source_agent_id = payload.get("source_agent_id")
        dispatch_request_id = payload.get("dispatch_request_id")

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

        if isinstance(origin_kernel_session_id, str) and origin_kernel_session_id.strip():
            dispatch_payload["origin_kernel_session_id"] = origin_kernel_session_id.strip()
        if isinstance(source_agent_id, str) and source_agent_id.strip():
            dispatch_payload["source_agent_id"] = source_agent_id.strip()
        if isinstance(dispatch_request_id, str) and dispatch_request_id.strip():
            dispatch_payload["dispatch_request_id"] = dispatch_request_id.strip()

        try:
            ack = await manager.send_agent_message(dispatch_payload)
            await self._sync_direct_session(
                ack=ack,
                text=text.strip(),
                origin_kernel_session_id=origin_kernel_session_id,
                source_agent_id=source_agent_id,
                dispatch_request_id=dispatch_request_id,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"IM dispatch failed: {exc}"}

        return {
            "ok": True,
            "to": to.strip(),
            "text": text.strip(),
            **ack.as_dict(),
        }

    async def _sync_direct_session(
        self,
        *,
        ack: Any,
        text: str,
        origin_kernel_session_id: object,
        source_agent_id: object,
        dispatch_request_id: object,
    ) -> None:
        if getattr(ack, "target_kind", None) != "user_id":
            return
        if not isinstance(origin_kernel_session_id, str) or not origin_kernel_session_id.strip():
            return
        if not isinstance(source_agent_id, str) or not source_agent_id.strip():
            source_agent_id = getattr(ack, "source_agent_id", None)
        if not isinstance(source_agent_id, str) or not source_agent_id.strip():
            return
        if self._session_store is None or self._kernel_client is None:
            return

        bind_conversation_session(
            store=self._session_store,
            channel_name=self._direct_channel_name,
            conversation_id=str(getattr(ack, "conversation_id")),
            agent_id=source_agent_id.strip(),
            kernel_session_id=origin_kernel_session_id.strip(),
        )
        append_idempotency_key = None
        if isinstance(dispatch_request_id, str) and dispatch_request_id.strip():
            append_idempotency_key = f"dispatch-sync:{dispatch_request_id.strip()}"
        self._kernel_client.append_message(
            session_id=origin_kernel_session_id.strip(),
            role="assistant",
            content=text,
            message_id=str(getattr(ack, "message_id")),
            metadata={
                "source": "send_message",
                "conversation_id": str(getattr(ack, "conversation_id")),
                "target_kind": str(getattr(ack, "target_kind")),
                "target_id": str(getattr(ack, "target_id")),
                "source_agent_id": source_agent_id.strip(),
            },
            idempotency_key=append_idempotency_key,
        )

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
