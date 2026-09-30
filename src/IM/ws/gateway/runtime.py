"""Thin Gateway WebSocket endpoint runtime and authenticated dispatch."""

from __future__ import annotations

import asyncio

from anyio import CancelScope

from fastapi import WebSocket, WebSocketDisconnect

from .channel_control import GatewayChannelControl
from .control import GatewayControl
from .execution import GatewayExecution
from .protocol import (
    _boundary_rejection_code,
    _decode_message,
    _require_dict,
    _require_message_type,
    _require_text,
)
from .relay import GatewayRelay
from .sessions import GatewaySessions
from .work import GatewayWork
from .task_graphs import GatewayTaskGraphs


class GatewayRuntime:
    """Accept Gateway frames, authorize them, and dispatch to their state owner."""

    _SUPPORTED_UPSTREAM_TYPES = frozenset(
        {
            "node.heartbeat",
            "agent.work.append",
            "conversation.query",
            "task_graph.command",
            "agent.work.permission.result",
            "node.report",
            "node.delivery_receipt",
            "agent.config",
            "agent.created",
            "agent.config.apply.result",
            "agent.config.operation.status.result",
            "agent.capabilities",
            "node.capabilities",
            "agent.prompt.preview",
            "node.prompt.preview",
            "node.heartbeat.md",
            "node.cron.jobs",
            "node.cron.delete",
            "node.skills.usage",
            "session.fork.result",
            "node.distill.prompt",
            "channel.reconcile.result",
            "channels.bootstrap",
            "channel.status",
            "channel.runtime_metadata",
            "agent.message",
            "agent.config.boundary",
            "node.streaming_delta",
            "node.system_message",
        }
    )

    def __init__(
        self,
        *,
        sessions: GatewaySessions,
        control: GatewayControl,
        channel_control: GatewayChannelControl,
        relay: GatewayRelay,
        execution: GatewayExecution,
        work: GatewayWork | None = None,
        task_graphs: GatewayTaskGraphs | None = None,
    ) -> None:
        self._sessions = sessions
        self._control = control
        self._channel_control = channel_control
        self._relay = relay
        self._execution = execution
        self._work = work
        self._task_graphs = task_graphs

    async def serve(
        self, websocket: WebSocket, *, authenticated_owner_id: str = ""
    ) -> None:
        """Run one authenticated WebSocket until its current registration disconnects."""
        await websocket.accept()
        node_id: str | None = None
        gate = getattr(
            getattr(websocket.scope.get("app"), "state", None), "company_gate", None
        )
        # An HTTP request can own the gate while waiting for an RPC response.
        # Keep reading those responses even when an earlier mutation is queued.
        rpc_results = {
            "agent.config",
            "agent.created",
            "agent.config.apply.result",
            "agent.config.operation.status.result",
            "agent.capabilities",
            "node.capabilities",
            "agent.prompt.preview",
            "node.prompt.preview",
            "node.heartbeat.md",
            "node.cron.jobs",
            "node.cron.delete",
            "node.skills.usage",
            "session.fork.result",
            "node.distill.prompt",
            "agent.work.permission.result",
        }
        pending = asyncio.Queue(maxsize=256)
        pending_bytes = 0

        async def dispatch(message_type, body):
            nonlocal node_id
            response = await self.handle_message(
                websocket=websocket,
                message_type=message_type,
                payload=body,
                authenticated_owner_id=authenticated_owner_id,
            )
            if response is not None:
                if response.get("type") == "error" and isinstance(
                    response.get("payload"), dict
                ):
                    response["payload"].setdefault("message_type", message_type)
                await websocket.send_json(response)
            if (
                message_type == "node.register"
                and response is not None
                and response.get("type") == "ack"
            ):
                node_id = str(body["node_id"])
                await self._channel_control.initialize_channel_control(node_id=node_id)
                await self._control.replay_submitted_permissions(node_id=node_id)

        async def read_frames():
            nonlocal pending_bytes
            while True:
                raw_message = await websocket.receive_text()
                payload = _decode_message(raw_message)
                message_type = _require_message_type(payload)
                body = _require_dict(payload.get("payload"), field_name="payload")
                if gate is None or message_type in rpc_results:
                    await dispatch(message_type, body)
                elif message_type == "node.register":
                    async with gate:
                        await dispatch(message_type, body)
                else:
                    size = len(raw_message.encode("utf-8"))
                    if pending.full() or pending_bytes + size > 4 * 1024 * 1024:
                        await websocket.close(code=1013, reason="Gateway input backlog")
                        return
                    pending_bytes += size
                    pending.put_nowait((message_type, body, size))

        async def apply_frames():
            nonlocal pending_bytes
            while True:
                message_type, body, size = await pending.get()
                try:
                    async with gate:
                        # handle_message rechecks current authority after queueing.
                        await dispatch(message_type, body)
                finally:
                    pending_bytes -= size
                    pending.task_done()

        tasks = [
            asyncio.create_task(read_frames()),
            asyncio.create_task(apply_frames()),
        ]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        finally:
            # ASGI disconnect cancels the endpoint scope; finish both owned tasks
            # and registration cleanup before returning to that scope.
            with CancelScope(shield=True):
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                if node_id is not None:
                    await self._sessions.disconnect(
                        node_id=node_id, expected_websocket=websocket
                    )

    async def handle_message(
        self,
        *,
        websocket: WebSocket,
        message_type: str,
        payload: dict[str, object],
        authenticated_owner_id: str = "",
    ) -> dict[str, object] | None:
        """Dispatch one decoded Gateway protocol message to its concrete owner."""
        if message_type == "node.register":
            try:
                return await self._sessions.register(
                    websocket=websocket,
                    payload=payload,
                    authenticated_owner_id=authenticated_owner_id,
                )
            except ValueError as exc:
                return {
                    "type": "error",
                    "payload": {
                        "message_type": message_type,
                        "code": "bad_payload",
                        "message": str(exc),
                    },
                }
        if message_type not in self._SUPPORTED_UPSTREAM_TYPES:
            return {
                "type": "error",
                "payload": {
                    "code": "unsupported_message_type",
                    "message": message_type,
                },
            }
        if authenticated_owner_id:
            try:
                _require_text(payload.get("node_id"), field_name="node_id")
            except ValueError as exc:
                return {
                    "type": "error",
                    "payload": {"code": "bad_payload", "message": str(exc)},
                }
            await self._sessions.authorize(
                websocket=websocket,
                payload=payload,
                authenticated_owner_id=authenticated_owner_id,
            )
        if message_type == "task_graph.command":
            if (
                self._task_graphs is None
                or not await self._sessions.is_registered_sender(
                    websocket=websocket, node_id=str(payload.get("node_id", ""))
                )
            ):
                return {"type": "error", "payload": {"code": "node_not_registered"}}
            return await self._task_graphs.command(payload=payload)
        if message_type in {
            "agent.work.append",
            "conversation.query",
            "agent.work.permission.result",
        }:
            if self._work is None or not await self._sessions.is_registered_sender(
                websocket=websocket, node_id=str(payload.get("node_id", ""))
            ):
                return {"type": "error", "payload": {"code": "node_not_registered"}}
            handler = {
                "agent.work.append": self._work.append,
                "conversation.query": self._work.query,
                "agent.work.permission.result": self._work.permission_result,
            }[message_type]
            return await handler(payload=payload)
        handlers = {
            "node.heartbeat": self._sessions.heartbeat,
            "node.report": self._execution.handle_report,
            "node.delivery_receipt": self._relay.handle_delivery_receipt,
            "agent.config": self._control._handle_agent_config,
            "agent.created": self._control._handle_agent_created,
            "agent.config.apply.result": self._control._handle_agent_config_apply_result,
            "agent.config.operation.status.result": self._control._handle_agent_config_operation_status_result,
            "agent.capabilities": self._control._handle_agent_capabilities,
            "node.capabilities": self._control._handle_node_capabilities,
            "agent.prompt.preview": self._control._handle_prompt_preview,
            "node.prompt.preview": self._control._handle_node_prompt_preview,
            "node.heartbeat.md": self._control._handle_heartbeat_md,
            "node.cron.jobs": self._control._handle_cron_jobs,
            "node.cron.delete": self._control._handle_cron_delete,
            "node.skills.usage": self._control._handle_skills_usage,
            "session.fork.result": self._control._handle_session_fork_result,
            "node.distill.prompt": self._control._handle_distill_prompt,
            "channel.reconcile.result": lambda *, payload: (
                self._channel_control._handle_channel_reconcile_result(
                    websocket=websocket, payload=payload
                )
            ),
            "channels.bootstrap": lambda *, payload: (
                self._channel_control._handle_channel_bootstrap(
                    websocket=websocket, payload=payload
                )
            ),
            "channel.status": lambda *, payload: (
                self._channel_control._handle_channel_status(
                    websocket=websocket, payload=payload
                )
            ),
            "channel.runtime_metadata": lambda *, payload: (
                self._channel_control._handle_channel_runtime_metadata(
                    websocket=websocket, payload=payload
                )
            ),
            "agent.message": self._relay.handle_agent_message,
            "node.streaming_delta": self._relay.handle_streaming_delta,
            "node.system_message": self._relay.handle_system_message,
        }
        if message_type == "agent.config.boundary":
            try:
                return await self._execution.handle_agent_config_boundary(
                    payload=payload
                )
            except ValueError as exc:
                return {
                    "type": "error",
                    "payload": {
                        "code": _boundary_rejection_code(exc),
                        "message": str(exc),
                        "message_type": message_type,
                    },
                }
        handler = handlers[message_type]
        if message_type == "node.streaming_delta":
            try:
                self._execution.authorize_streaming_payload(payload)
                return await handler(payload=payload)
            except ValueError as exc:
                return {
                    "type": "error",
                    "payload": {"code": "bad_payload", "message": str(exc)},
                }
        return await handler(payload=payload)
