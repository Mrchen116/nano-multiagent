"""Internal Gateway HTTP dispatch endpoint for agent-to-agent message routing.

Exposes ``POST /internal/dispatch`` so that product tools (e.g. ``send_message``)
running inside the kernel can post outbound messages back through the Gateway's
existing IM routing layer without requiring a separate process or service.
"""

from __future__ import annotations

import asyncio
import json
import logging
from threading import Lock
from typing import TYPE_CHECKING, Any, Callable, Mapping

if TYPE_CHECKING:
    from agent.sdk import Kernel

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.session_binder import (
    ConversationBindingRequest,
    GatewaySessionBinder,
    SessionProvenance,
)


_log = logging.getLogger(__name__)


class InternalDispatchEndpoint:
    """Publish the URL of the listener that is currently accepting dispatches.

    The runtime writes this owner only after ``aiohttp`` has successfully bound a
    socket. Session creation reads it later, so metadata can never advertise a
    configured port that failed to listen.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._url: str | None = None

    def publish(self, *, host: str, port: int) -> str:
        """Publish and return the exact internal dispatch URL for a bound socket."""

        url = f"http://{host}:{port}/internal/dispatch"
        with self._lock:
            self._url = url
        return url

    def clear(self) -> None:
        """Remove a listener URL that is no longer accepting requests."""

        with self._lock:
            self._url = None

    def current_url(self) -> str | None:
        """Return the currently bound URL, or ``None`` before/after listener life."""

        with self._lock:
            return self._url


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
        kernel: Kernel | None = None,
        session_binder: GatewaySessionBinder | None = None,
        direct_channel_name: str = "web_relay",
        global_inbox: Any | None = None,
        work_recorder: Any | None = None,
        shadow_sync: Any | None = None,
        outbound_router: OutboundRouter | None = None,
    ) -> None:
        self._im_connection_manager = im_connection_manager
        self._kernel_client = kernel_client
        self._kernel = kernel
        self._session_binder = session_binder
        self._direct_channel_name = direct_channel_name
        self._global_inbox = global_inbox
        self._work_recorder = work_recorder
        self._shadow_sync = shadow_sync
        self._outbound_router = outbound_router
        self._sealed = False

    def seal(self) -> None:
        """Synchronously reject requests that have not entered ``handle`` yet."""

        self._sealed = True

    async def handle(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Process one dispatch request and return a response dict.

        Args:
            payload: Parsed request body; must contain ``text`` and ``to``.

        Returns:
            ``{"ok": True}`` on success or ``{"ok": False, "error": "..."}`` on failure.
        """

        if self._sealed:
            return {
                "ok": False,
                "error": "Gateway is shutting down; cannot dispatch message",
            }

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

        if (
            isinstance(origin_kernel_session_id, str)
            and origin_kernel_session_id.strip()
        ):
            dispatch_payload["origin_kernel_session_id"] = (
                origin_kernel_session_id.strip()
            )
        if isinstance(source_agent_id, str) and source_agent_id.strip():
            dispatch_payload["source_agent_id"] = source_agent_id.strip()
        if isinstance(dispatch_request_id, str) and dispatch_request_id.strip():
            dispatch_payload["dispatch_request_id"] = dispatch_request_id.strip()

        provenance = self._capture_source_provenance(
            origin_kernel_session_id,
            source_agent_id,
        )
        if (
            self._session_binder is not None
            and isinstance(origin_kernel_session_id, str)
            and origin_kernel_session_id.strip()
            and isinstance(source_agent_id, str)
            and source_agent_id.strip()
            and provenance is None
        ):
            return {
                "ok": False,
                "error": "origin Kernel session provenance is not registered",
            }
        if provenance is not None and provenance.agent.config.work_mode == "global":
            return await self._dispatch_global(payload, dispatch_payload, provenance)
        try:
            context_revision = payload.get("context_revision")
            origin_run_id = payload.get("origin_run_id")
            source_binding = (
                self._session_binder.find_by_kernel_session_id(origin_kernel_session_id)
                if self._session_binder is not None
                and isinstance(origin_kernel_session_id, str)
                and context_revision is not None
                else None
            )
            same_group = (
                source_binding is not None
                and source_binding.reply_context.channel_name
                == self._direct_channel_name
                and source_binding.reply_context.target_chat_id == to.strip()
            )
            if same_group:
                if (
                    self._kernel is None
                    or not isinstance(origin_run_id, str)
                    or not isinstance(context_revision, int)
                    or isinstance(context_revision, bool)
                ):
                    return {
                        "ok": False,
                        "error": "group output run identity is missing",
                    }
                draft_id = f"draft:{origin_run_id}:{dispatch_request_id}"
                send_task: asyncio.Task | None = None

                def enqueue() -> None:
                    nonlocal send_task
                    # This callback runs under the Kernel's short acceptance lock.
                    # Only enqueue here; the network and ACK run after lock release.
                    send_task = asyncio.create_task(
                        manager.send_agent_message(dict(dispatch_payload))
                    )

                decision = self._kernel.try_commit_output(
                    session_id=origin_kernel_session_id,
                    expected_run_id=origin_run_id,
                    context_revision=context_revision,
                    publish=enqueue,
                    draft={
                        "draft_id": draft_id,
                        "source": "send_message",
                        "text": text.strip(),
                        "tool_call_id": dispatch_request_id,
                    },
                )
                if decision == "stale":
                    return {
                        "ok": False,
                        "status": "held_for_revalidation",
                        "draft_id": draft_id,
                    }
                if decision != "committed":
                    return {
                        "ok": False,
                        "error": "group output run is no longer active",
                    }
                assert send_task is not None
                ack = await send_task
            else:
                ack = await manager.send_agent_message(dispatch_payload)
            await self._sync_direct_session(
                ack=ack,
                text=text.strip(),
                origin_kernel_session_id=origin_kernel_session_id,
                source_agent_id=source_agent_id,
                dispatch_request_id=dispatch_request_id,
                provenance=provenance,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"IM dispatch failed: {exc}"}

        return {
            "ok": True,
            "to": to.strip(),
            "text": text.strip(),
            **ack.as_dict(),
        }

    async def _dispatch_global(
        self,
        payload: Mapping[str, Any],
        dispatch: dict[str, Any],
        provenance: SessionProvenance,
    ) -> dict[str, Any]:
        inbox = self._global_inbox
        recorder = self._work_recorder
        if inbox is None or recorder is None:
            return {"ok": False, "error": "global dispatch service unavailable"}
        agent_id = provenance.agent.agent_id
        session_id = provenance.kernel_session_id
        target = dispatch["to"]
        target_info = inbox.get_target(agent_id, target)
        if target_info and target_info.get("permission_status") != "allowed":
            return {"ok": False, "error": "target_not_accessible"}
        if target.startswith("local:"):
            if (
                target_info
                and not target_info.get("conversation_id")
                and self._shadow_sync is not None
            ):
                saga_id = (
                    (target_info.get("reply_context") or {})
                    .get("metadata", {})
                    .get("global_shadow_saga_id")
                )
                anchor = self._shadow_sync.resolved_anchor(saga_id) if saga_id else None
                if anchor is not None:
                    target_info = inbox.update_target(
                        agent_id, target, conversation_id=anchor.conversation_id
                    )
            if not target_info or not target_info.get("conversation_id"):
                return {
                    "ok": False,
                    "error": "source_unavailable: conversation has not synchronized",
                }
            dispatch["to"] = target_info["conversation_id"]
        metadata = (target_info or {}).get("reply_context", {}) or {}
        native_group = bool(
            target_info
            and target_info.get("kind") == "group"
            and target_info.get("channel") == "web_relay"
            and not metadata.get("metadata", {}).get("external_source")
        )
        call_id = payload.get("dispatch_request_id")
        run_id = payload.get("origin_run_id")
        revision = payload.get("context_revision")
        if native_group and (
            not isinstance(run_id, str)
            or not run_id.strip()
            or type(revision) is not int
        ):
            return {"ok": False, "error": "global output run identity is missing"}
        draft_id = f"draft:{run_id}:{call_id}"
        facts = {
            "tool_call_id": call_id,
            "run_id": run_id,
            "target": target,
            "text": dispatch["text"],
            "draft_id": draft_id,
        }
        try:
            if native_group:
                async with inbox.target_lock(agent_id, target):
                    blocking = inbox.blocking_entries(agent_id, target)
                    if blocking:
                        recorder.record(
                            agent_id=agent_id,
                            session_id=session_id,
                            event_type="draft_withheld",
                            event_id=f"withheld:{session_id}:{call_id}",
                            payload={
                                **facts,
                                "source_refs": [
                                    {
                                        "conversation_id": target,
                                        "message_id": entry.get("message_id"),
                                        "entry_seq": entry["seq"],
                                    }
                                    for entry in blocking
                                ],
                            },
                        )
                        return {
                            "ok": False,
                            "status": "held_for_revalidation",
                            "draft_id": draft_id,
                        }
                    send_task = None

                    def enqueue() -> None:
                        nonlocal send_task
                        send_task = asyncio.create_task(
                            self._im_connection_manager.send_agent_message(
                                dict(dispatch)
                            )
                        )

                    decision = self._kernel.try_commit_output(
                        session_id=session_id,
                        expected_run_id=run_id,
                        context_revision=revision,
                        publish=enqueue,
                        draft={
                            "draft_id": draft_id,
                            "source": "send_message",
                            "text": dispatch["text"],
                            "tool_call_id": call_id,
                        },
                    )
                    if decision == "stale":
                        recorder.record(
                            agent_id=agent_id,
                            session_id=session_id,
                            event_type="draft_withheld",
                            event_id=f"withheld:{session_id}:{call_id}",
                            payload=facts,
                        )
                        return {
                            "ok": False,
                            "status": "held_for_revalidation",
                            "draft_id": draft_id,
                        }
                    if decision != "committed":
                        return {
                            "ok": False,
                            "error": "global output run is no longer active",
                        }
                ack = await send_task
            else:
                ack = await self._im_connection_manager.send_agent_message(dispatch)
            dispatch_event_id = f"dispatch:{session_id}:{call_id}"
            channel_name = metadata.get("channel_name")
            if (
                channel_name
                and channel_name != self._direct_channel_name
                and recorder.store.get_work_event(dispatch_event_id) is None
            ):
                if self._outbound_router is None:
                    raise RuntimeError("external delivery router unavailable")
                # The IM ACK confirms only the shadow bubble. The captured source
                # route must also succeed before this explicit reply is delivered.
                await self._outbound_router.send_text_async(
                    text=dispatch["text"],
                    reply_context=ReplyContext(
                        channel_name=channel_name,
                        target_chat_id=metadata["target_chat_id"],
                        thread_id=metadata.get("thread_id"),
                        metadata={
                            **metadata.get("metadata", {}),
                            "reply_dedupe_key": dispatch_event_id,
                        },
                    ),
                )
            try:
                recorder.record(
                    agent_id=agent_id,
                    session_id=session_id,
                    event_type="dispatch_confirmed",
                    event_id=dispatch_event_id,
                    payload={**facts, **ack.as_dict()},
                )
            except Exception:
                # Both required deliveries have succeeded. Reporting failure here
                # invites the model to send the same message with a new call id.
                _log.exception(
                    "global dispatch confirmation recording failed event=%s",
                    dispatch_event_id,
                )
            return {"ok": True, "to": target, "text": dispatch["text"], **ack.as_dict()}
        except Exception as exc:
            return {"ok": False, "error": f"IM dispatch failed: {exc}"}

    def build_query_handler(self, tool_name: str) -> Callable:
        """Build a loopback query handler with actual Session provenance checks."""
        from aiohttp import web

        async def handle(request: Any) -> Any:
            try:
                payload = await request.json()
                if self._sealed or self._global_inbox is None:
                    raise ValueError("source_unavailable")
                agent_id = payload.get("source_agent_id")
                session_id = payload.get("origin_kernel_session_id")
                call_id = payload.get("tool_call_id")
                if (
                    self._capture_source_provenance(session_id, agent_id) is None
                    or not isinstance(call_id, str)
                    or not call_id
                ):
                    raise ValueError("scope_not_allowed")
                result = await self._global_inbox.execute(
                    tool_name,
                    agent_id=agent_id,
                    session_id=session_id,
                    tool_call_id=call_id,
                    args=payload.get("args", {}),
                )
                return web.json_response({"ok": True, "result": result})
            except (ValueError, TypeError) as exc:
                return web.json_response({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                return web.json_response(
                    {"ok": False, "error": f"source_unavailable: {exc}"}, status=503
                )

        return handle

    async def _sync_direct_session(
        self,
        *,
        ack: Any,
        text: str,
        origin_kernel_session_id: object,
        source_agent_id: object,
        dispatch_request_id: object,
        provenance: SessionProvenance | None,
    ) -> None:
        if getattr(ack, "target_kind", None) != "user_id":
            return
        if (
            not isinstance(origin_kernel_session_id, str)
            or not origin_kernel_session_id.strip()
        ):
            return
        if not isinstance(source_agent_id, str) or not source_agent_id.strip():
            source_agent_id = getattr(ack, "source_agent_id", None)
        if not isinstance(source_agent_id, str) or not source_agent_id.strip():
            return
        binder = self._session_binder
        if binder is None or self._kernel_client is None or provenance is None:
            return
        normalized_agent_id = source_agent_id.strip()
        if provenance.agent.agent_id != normalized_agent_id:
            return

        binder.bind_conversation(
            ConversationBindingRequest(
                channel_name=self._direct_channel_name,
                conversation_id=str(getattr(ack, "conversation_id")),
                agent_id=normalized_agent_id,
                kernel_session_id=origin_kernel_session_id.strip(),
                guard=provenance.guard,
            ),
            provenance.agent,
        )
        append_idempotency_key = None
        if isinstance(dispatch_request_id, str) and dispatch_request_id.strip():
            append_idempotency_key = f"dispatch-sync:{dispatch_request_id.strip()}"
        # The stateless kernel needs the origin session's workspace_root to locate
        # its JSONL; resolve it from the source agent's config.
        origin_workspace_root = provenance.agent.config.workspace_root
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
            workspace_root=origin_workspace_root,
        )

    def _capture_source_provenance(
        self,
        origin_kernel_session_id: object,
        source_agent_id: object,
    ) -> SessionProvenance | None:
        """Capture origin session facts before the IM acknowledgement await."""

        if (
            not isinstance(origin_kernel_session_id, str)
            or not origin_kernel_session_id.strip()
            or not isinstance(source_agent_id, str)
            or not source_agent_id.strip()
            or self._session_binder is None
        ):
            return None
        return self._session_binder.capture_session_provenance(
            origin_kernel_session_id.strip(),
            expected_agent_id=source_agent_id.strip(),
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
            status = (
                200
                if result.get("ok") or result.get("status") == "held_for_revalidation"
                else 503
            )
            return Response(
                status=status,
                content_type="application/json",
                text=json.dumps(result),
            )

        return _handle
