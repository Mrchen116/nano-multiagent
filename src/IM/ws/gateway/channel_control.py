from __future__ import annotations

import asyncio
import contextlib
import logging
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

from IM.infra.channel_control_store import ChannelControlStore, ChannelManifest
from .protocol import (
    _not_registered_error,
    _optional_int,
    _require_text,
)

_logger = logging.getLogger(__name__)

from .sessions import GatewaySessions


class GatewayChannelControl:
    """Own Channel initialization, manifest reconciliation, and runtime status ingress."""

    def __init__(
        self,
        *,
        sessions: GatewaySessions,
        channel_control_store: ChannelControlStore | None,
        lock: asyncio.Lock,
    ) -> None:
        self._sessions = sessions
        self._channel_control_store = channel_control_store
        self._lock = lock
        self._channel_initialization_locks: dict[str, asyncio.Lock] = {}

    async def push_reconcile(self, manifest: ChannelManifest) -> bool:
        """Push one authoritative full desired snapshot to its connected node."""
        return await self._sessions.send(
            target_node_id=manifest.node_id,
            message_type="channel.reconcile",
            payload=manifest.as_payload(request_id=uuid4().hex),
        )

    async def push_reconnect(
        self, *, target_node_id: str, channel_id: str, channel_revision: int
    ) -> bool:
        """Push one ephemeral reconnect action without changing desired state."""
        return await self._sessions.send(
            target_node_id=target_node_id,
            message_type="channel.reconnect",
            payload={
                "channel_id": channel_id,
                "channel_revision": channel_revision,
            },
        )

    async def initialize_channel_control(self, *, node_id: str) -> bool:
        """Initialize once after register/bind or replay current desired state."""
        store = self._channel_control_store
        if store is None:
            return False
        lock = self._channel_initialization_locks.setdefault(node_id, asyncio.Lock())
        async with lock:
            connection = await self._sessions.snapshot_connection(node_id=node_id)
            if (
                connection is None
                or not connection.credential_key_id
                or not connection.credential_algorithm
                or not connection.credential_public_key
            ):
                return False
            durable_owner = store.current_owner_for_node(node_id=node_id)
            if durable_owner and durable_owner != connection.owner_id:
                store.remove_node_public_key(node_id=node_id)
                await self._sessions.disconnect(
                    node_id=node_id, expected_websocket=connection.websocket
                )
                with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                    await connection.websocket.close(code=1008)
                return False
            registered = store.register_bound_node_public_key(
                node_id=node_id,
                key_id=connection.credential_key_id,
                algorithm=connection.credential_algorithm,
                public_key=connection.credential_public_key,
            )
            if not registered:
                return False
            if connection.capabilities.get("channel_bootstrap") is not True:
                return True
            state, manifest = store.prepare_initialization(node_id=node_id)
            if state == "bootstrap_required":
                return await self._sessions.send(
                    target_node_id=node_id,
                    message_type="channels.bootstrap.request",
                    payload={
                        "request_id": uuid4().hex,
                        "node_id": node_id,
                        "owner_id": store.current_owner_for_node(node_id=node_id),
                    },
                )
            if manifest is not None:
                return await self.push_reconcile(manifest)
            return state == "waiting_for_owner"

    async def _handle_channel_reconcile_result(
        self, *, websocket: WebSocket, payload: dict[str, object]
    ) -> dict[str, object]:
        """Persist an applied head and acknowledge the Gateway upstream FIFO item."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        if not await self._sessions.is_registered_sender(
            websocket=websocket, node_id=node_id
        ):
            return _not_registered_error(node_id=node_id)
        manifest_revision = _optional_int(payload.get("manifest_revision"))
        if manifest_revision is None:
            raise ValueError("manifest_revision is required")
        legacy_outcomes = payload.get("outcomes")
        modern = "outcome" in payload
        outcome = str(payload.get("outcome") or "")
        applied_channel_ids = payload.get("applied_channel_ids")
        failures = payload.get("failures")
        if not modern:
            normalized = legacy_outcomes if isinstance(legacy_outcomes, list) else []
            applied_channel_ids = [
                item.get("channel_id")
                for item in normalized
                if isinstance(item, dict) and item.get("outcome") == "applied"
            ]
            failures = [
                item
                for item in normalized
                if isinstance(item, dict) and item.get("outcome") != "applied"
            ]
            outcome = "retryable_failed" if failures else "applied"
        acknowledgement: dict[str, object] = {
            "head_outcome": "accepted",
            "removal_token_outcomes": [],
        }
        if self._channel_control_store is not None:
            acknowledgement = self._channel_control_store.record_reconcile_result(
                node_id=node_id,
                manifest_revision=manifest_revision,
                outcome=outcome,
                applied_channel_ids=applied_channel_ids,
                removal_outcomes=payload.get("removal_outcomes"),
                failures=failures,
            )
        if modern:
            return {
                "type": "channels.reconcile.result.ack",
                "payload": {
                    "request_id": request_id,
                    "manifest_revision": manifest_revision,
                    **acknowledgement,
                },
            }
        return {
            "type": "ack",
            "payload": {
                "message_type": "channel.reconcile.result",
                "request_id": request_id,
            },
        }

    async def _handle_channel_bootstrap(
        self, *, websocket: WebSocket, payload: dict[str, object]
    ) -> dict[str, object]:
        """Commit a legacy snapshot once and return its authoritative manifest."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        if not await self._sessions.is_registered_sender(
            websocket=websocket, node_id=node_id
        ):
            return _not_registered_error(node_id=node_id)
        store = self._channel_control_store
        if store is None:
            return {
                "type": "error",
                "payload": {
                    "code": "channel_control_unavailable",
                    "request_id": request_id,
                },
            }
        outcome, manifest = store.bootstrap_channels(
            node_id=node_id, items=payload.get("items")
        )
        return {
            "type": "channels.bootstrap.result",
            "payload": {
                "request_id": request_id,
                "outcome": outcome,
                "manifest": manifest.as_payload(request_id=uuid4().hex),
            },
        }

    async def _handle_channel_status(
        self, *, websocket: WebSocket, payload: dict[str, object]
    ) -> dict[str, object]:
        """Return a normal correlated result for every semantic status outcome."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        if not await self._sessions.is_registered_sender(
            websocket=websocket, node_id=node_id
        ):
            return _not_registered_error(node_id=node_id)
        result = (
            self._channel_control_store.record_status_result(payload)
            if self._channel_control_store is not None
            else None
        )
        outcome = result.outcome if result is not None else "terminal_channel_removed"
        if (
            outcome == "accepted"
            and result is not None
            and result.owner_id is not None
            and result.agent_id is not None
            and result.channel_id is not None
        ):
            await self._sessions.broadcast_channel_status_change(
                owner_id=result.owner_id,
                agent_id=result.agent_id,
                channel_id=result.channel_id,
            )
        return {
            "type": "channel.status.result",
            "payload": {"request_id": request_id, "outcome": outcome},
        }

    async def _handle_channel_runtime_metadata(
        self, *, websocket: WebSocket, payload: dict[str, object]
    ) -> dict[str, object]:
        """Apply generation-scoped provider identity metadata and correlate result."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        if not await self._sessions.is_registered_sender(
            websocket=websocket, node_id=node_id
        ):
            return _not_registered_error(node_id=node_id)
        outcome = (
            self._channel_control_store.record_provider_metadata(payload)
            if self._channel_control_store is not None
            else "terminal_channel_removed"
        )
        return {
            "type": "channel.runtime_metadata.result",
            "payload": {"request_id": request_id, "outcome": outcome},
        }
