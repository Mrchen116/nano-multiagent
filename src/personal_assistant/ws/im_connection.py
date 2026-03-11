"""Gateway-side IM websocket client with reconnect/backoff and downstream dispatch."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.reporter.upstream_reporter import UpstreamReporter


class ClientWebSocket(Protocol):
    """Minimal async websocket protocol required by ``IMConnectionManager``."""

    async def send(self, data: str) -> None:
        """Send one serialized text frame."""

    async def recv(self) -> str:
        """Receive the next serialized text frame."""

    async def close(self) -> None:
        """Close the underlying websocket connection."""


ConnectFn = Callable[[str, Mapping[str, str]], Awaitable[ClientWebSocket]]
SleepFn = Callable[[float], Awaitable[None]]
HeartbeatTrigger = Callable[[str, str], None]


@dataclass(frozen=True, slots=True)
class IMConnectionConfig:
    """Configure IM websocket connectivity and reconnect behavior.

    Args:
        url: IM service base URL or websocket URL.
        token: Optional bearer token for upstream auth.
        reconnect_initial_seconds: Initial reconnect delay after failure.
        reconnect_max_seconds: Maximum reconnect delay cap.
    """

    url: str
    token: str | None = None
    reconnect_initial_seconds: float = 1.0
    reconnect_max_seconds: float = 60.0

    def websocket_url(self) -> str:
        """Return the normalized websocket endpoint URL for the IM gateway socket."""

        parsed = urlparse(self.url)
        if parsed.scheme in {"ws", "wss"}:
            base = self.url.rstrip("/")
        elif parsed.scheme == "https":
            base = f"wss://{parsed.netloc}{parsed.path}".rstrip("/")
        elif parsed.scheme == "http":
            base = f"ws://{parsed.netloc}{parsed.path}".rstrip("/")
        else:
            raise ValueError("IM websocket URL must use http(s) or ws(s)")
        if base.endswith("/im/ws/gateway"):
            return base
        return f"{base}/im/ws/gateway"


class IMConnectionManager:
    """Maintain the optional gateway -> IM websocket connection.

    Args:
        config: Connection endpoint and reconnect policy.
        reporter: Upstream frame builder used after connect and during reporting.
        relay_adapter: Downstream relay adapter that receives ``relay.message`` pushes.
        sync_client: Optional config sync handler.
        heartbeat_trigger: Optional local callback for ``heartbeat.trigger`` pushes.
        connect: Async websocket connector implementation.
        sleep: Async sleep implementation used for reconnect backoff.

    Notes:
        When the socket drops, this manager only updates local state and retries later.
        It does not interrupt the gateway's local IM/channel execution path, preserving
        the NodeGateway-SPEC local-autonomy requirement.
    """

    def __init__(
        self,
        *,
        config: IMConnectionConfig,
        reporter: UpstreamReporter,
        relay_adapter: WebRelayAdapter,
        sync_client: ConfigSyncClient | None = None,
        heartbeat_trigger: HeartbeatTrigger | None = None,
        connect: ConnectFn,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self._config = config
        self._reporter = reporter
        self._relay_adapter = relay_adapter
        self._sync_client = sync_client
        self._heartbeat_trigger = heartbeat_trigger
        self._connect = connect
        self._sleep = sleep
        self._websocket: ClientWebSocket | None = None
        self._connected = False
        self._stop_requested = False
        self._reconnect_delay = config.reconnect_initial_seconds
        self._events: list[dict[str, object]] = []

    @property
    def connected(self) -> bool:
        """Report whether the IM websocket is currently connected."""

        return self._connected

    def event_log(self) -> tuple[dict[str, object], ...]:
        """Return an immutable snapshot of connection lifecycle events."""

        return tuple(self._events)

    async def connect_once(self) -> None:
        """Open the IM websocket, register the node, and reset reconnect backoff."""

        headers = {"User-Agent": "nano-multiagent-gateway"}
        if self._config.token is not None:
            headers["Authorization"] = f"Bearer {self._config.token}"
        websocket = await self._connect(self._config.websocket_url(), headers)
        self._websocket = websocket
        self._connected = True
        self._reconnect_delay = self._config.reconnect_initial_seconds
        self._events.append({"event": "connected", "url": self._config.websocket_url()})
        await self._send_frame("node.register", self._reporter.send_register())

    async def close(self) -> None:
        """Stop reconnect attempts and close the current websocket if present."""

        self._stop_requested = True
        websocket = self._websocket
        self._websocket = None
        self._connected = False
        if websocket is not None:
            await websocket.close()
        self._events.append({"event": "closed"})

    async def send_json(self, message_type: str, payload: Mapping[str, object]) -> None:
        """Send one gateway -> IM protocol frame over the active websocket."""

        await self._send_frame(message_type, dict(payload))

    async def run_forever(self) -> None:
        """Maintain the IM websocket until ``close`` is requested."""

        while not self._stop_requested:
            try:
                if not self._connected:
                    await self.connect_once()
                await self._listen_once()
            except Exception as exc:  # noqa: BLE001
                self._connected = False
                self._websocket = None
                self._events.append({"event": "disconnected", "error": str(exc)})
                if self._stop_requested:
                    break
                await self._sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._config.reconnect_max_seconds)

    async def _listen_once(self) -> None:
        websocket = self._require_websocket()
        raw = await websocket.recv()
        payload = _decode_message(raw)
        message_type = _require_text(payload.get("type"), field_name="type")
        body = payload.get("payload")
        if body is None:
            body = {}
        if not isinstance(body, Mapping):
            raise ValueError("payload must be an object")
        self._events.append({"event": "frame", "type": message_type})
        if message_type == "ack":
            return
        if message_type == "relay.message":
            self._relay_adapter.accept_relay(body)
            return
        if message_type == "config.sync":
            if self._sync_client is not None:
                self._sync_client.handle_notification(body)
            return
        if message_type == "heartbeat.trigger":
            if self._heartbeat_trigger is not None:
                agent_id = _require_text(body.get("agent_id"), field_name="agent_id")
                reason = _require_text(body.get("reason"), field_name="reason")
                self._heartbeat_trigger(agent_id, reason)
            return
        raise ValueError(f"unsupported downstream message type: {message_type}")

    async def _send_frame(self, message_type: str, payload: Mapping[str, object]) -> None:
        websocket = self._require_websocket()
        frame = json.dumps({"type": message_type, "payload": dict(payload)}, ensure_ascii=False)
        await websocket.send(frame)
        self._events.append({"event": "sent", "type": message_type})

    def _require_websocket(self) -> ClientWebSocket:
        websocket = self._websocket
        if websocket is None:
            raise RuntimeError("IM websocket is not connected")
        return websocket


def _decode_message(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("message must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("message must be a JSON object")
    return parsed


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()
