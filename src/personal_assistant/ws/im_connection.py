"""Gateway-side IM websocket client with reconnect/backoff and downstream dispatch."""
from __future__ import annotations

import asyncio
import contextlib
import json
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.reporter.upstream_reporter import UpstreamReporter, build_runtime_capabilities


@dataclass(slots=True)
class PendingFrame:
    """Track one queued upstream frame plus its optional ack waiter."""

    message_type: str
    payload: dict[str, object]
    ack_future: asyncio.Future[dict[str, object]] | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class IMDispatchAck:
    """Canonical subset returned by IM after one agent.message dispatch."""

    conversation_id: str
    message_id: str
    target_kind: str
    target_id: str
    source_agent_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "IMDispatchAck":
        return cls(
            conversation_id=_require_text(payload.get("conversation_id"), field_name="conversation_id"),
            message_id=_require_text(payload.get("message_id"), field_name="message_id"),
            target_kind=_require_text(payload.get("target_kind"), field_name="target_kind"),
            target_id=_require_text(payload.get("target_id"), field_name="target_id"),
            source_agent_id=_require_text(payload.get("source_agent_id"), field_name="source_agent_id"),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "source_agent_id": self.source_agent_id,
        }


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
AgentConfigProvider = Callable[[str], Mapping[str, object] | None]
AgentCreateHandler = Callable[[Mapping[str, object]], Awaitable[Mapping[str, object] | None] | Mapping[str, object] | None]
AgentCapabilitiesProvider = Callable[[str, str], Awaitable[Mapping[str, object] | None] | Mapping[str, object] | None]
# Async callback that returns a fresh access token immediately before each connect attempt.
# Returning None means "no token available"; the caller should fall back or proceed without auth.
TokenGetter = Callable[[], Awaitable[str | None]]
# Called when IM sends a node.streaming_delta kind=permission_response.
# Payload keys: request_id, decision, message_id.  PA should POST the decision
# to the agent inbound endpoint to unpark the auto_mode_gate hook.
PermissionResponseHandler = Callable[[Mapping[str, object]], None]


@dataclass(frozen=True, slots=True)
class IMConnectionConfig:
    """Configure IM websocket connectivity and reconnect behavior.

    Args:
        url: IM service base URL or websocket URL.
        token: Optional bearer token for upstream auth.
        reconnect_initial_seconds: Initial reconnect delay after failure.
        reconnect_max_seconds: Maximum reconnect delay cap.
        heartbeat_interval_seconds: Delay between periodic node heartbeats while connected.
    """

    url: str
    token: str | None = None
    reconnect_initial_seconds: float = 1.0
    reconnect_max_seconds: float = 60.0
    heartbeat_interval_seconds: float = 30.0

    def normalized_heartbeat_interval_seconds(self) -> float | None:
        interval = self.heartbeat_interval_seconds
        if interval <= 0:
            return None
        return interval

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
        agent_config_provider: AgentConfigProvider | None = None,
        agent_create_handler: AgentCreateHandler | None = None,
        agent_capabilities_provider: AgentCapabilitiesProvider | None = None,
        token_getter: TokenGetter | None = None,
        permission_response_handler: PermissionResponseHandler | None = None,
        connect: ConnectFn,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self._config = config
        self._reporter = reporter
        self._relay_adapter = relay_adapter
        self._sync_client = sync_client
        self._heartbeat_trigger = heartbeat_trigger
        self._agent_config_provider = agent_config_provider
        self._agent_create_handler = agent_create_handler
        self._agent_capabilities_provider = agent_capabilities_provider
        # Called when IM pushes a permission_response so PA can POST it to the agent.
        self._permission_response_handler = permission_response_handler
        # token_getter is called on each connect attempt to supply a fresh access token.
        # When absent the static config.token is used (backwards-compatible behaviour).
        self._token_getter = token_getter
        self._connect = connect
        self._sleep = sleep
        self._websocket: ClientWebSocket | None = None
        self._connected = False
        self._stop_requested = False
        self._reconnect_delay = config.reconnect_initial_seconds
        self._events: list[dict[str, object]] = []
        self._pending_frames: deque[PendingFrame] = deque()
        self._awaiting_ack_type: str | None = None
        self._flush_lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None

    @property
    def connected(self) -> bool:
        """Report whether the IM websocket is currently connected."""

        return self._connected

    def event_log(self) -> tuple[dict[str, object], ...]:
        """Return an immutable snapshot of connection lifecycle events."""

        return tuple(self._events)

    async def connect_once(self) -> None:
        """Open the IM websocket, register the node, and flush buffered upstream frames.

        When ``token_getter`` is provided it is called before every connect attempt so
        each reconnect uses a freshly minted access token rather than the stale value
        that was loaded at startup.
        """

        headers = {"User-Agent": "nano-multiagent-gateway"}
        # Resolve token: prefer token_getter (dynamic refresh path) over static config.token.
        if self._token_getter is not None:
            dynamic_token = await self._token_getter()
            if dynamic_token is not None:
                headers["Authorization"] = f"Bearer {dynamic_token}"
        elif self._config.token is not None:
            headers["Authorization"] = f"Bearer {self._config.token}"
        websocket = await self._connect(self._config.websocket_url(), headers)
        self._websocket = websocket
        self._connected = True
        self._reconnect_delay = self._config.reconnect_initial_seconds
        self._events.append({"event": "connected", "url": self._config.websocket_url()})
        try:
            await self._send_frame("node.register", self._reporter.send_register())
            self._start_heartbeat_loop()
            await self._flush_pending_frames(raise_on_disconnect=True)
        except Exception as exc:  # noqa: BLE001
            await self._disconnect_current_websocket(exc)
            raise

    async def close(self) -> None:
        """Stop reconnect attempts and close the current websocket if present."""

        self._stop_requested = True
        self._stop_heartbeat_loop()
        websocket = self._websocket
        self._websocket = None
        self._connected = False
        if websocket is not None:
            await websocket.close()
        heartbeat_task = self._heartbeat_task
        if heartbeat_task is not None and heartbeat_task is not asyncio.current_task():
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task
        self._events.append({"event": "closed"})

    async def send_json(self, message_type: str, payload: Mapping[str, object]) -> None:
        """Queue one gateway -> IM protocol frame and flush it when the socket is available."""

        self._pending_frames.append(PendingFrame(message_type=message_type, payload=dict(payload)))
        await self._flush_pending_frames()

    async def send_json_await_ack(self, message_type: str, payload: Mapping[str, object]) -> dict[str, object]:
        """Queue one frame and wait until the matching ack payload arrives."""

        loop = asyncio.get_running_loop()
        ack_future: asyncio.Future[dict[str, object]] = loop.create_future()
        self._pending_frames.append(
            PendingFrame(message_type=message_type, payload=dict(payload), ack_future=ack_future)
        )
        await self._flush_pending_frames()
        return await ack_future

    async def send_agent_message(self, payload: Mapping[str, object]) -> IMDispatchAck:
        """Send one agent.message frame and return the parsed IM dispatch ack."""

        ack_payload = await self.send_json_await_ack("agent.message", payload)
        return IMDispatchAck.from_payload(ack_payload)

    async def run_forever(self) -> None:
        """Maintain the IM websocket until ``close`` is requested."""

        while not self._stop_requested:
            try:
                if not self._connected:
                    await self.connect_once()
                await self._listen_once()
            except Exception as exc:  # noqa: BLE001
                self._mark_disconnected(exc)
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
            self._ack_pending_frame(body)
            await self._flush_pending_frames()
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
        if message_type == "agent.config.get":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            agent_id = _require_text(body.get("agent_id"), field_name="agent_id")
            agent_payload = None
            if self._agent_config_provider is not None:
                payload = self._agent_config_provider(agent_id)
                if payload is not None:
                    agent_payload = dict(payload)
            await self.send_json(
                "agent.config",
                {
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "agent": agent_payload,
                },
            )
            return
        if message_type == "agent.create":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            agent_payload = _require_mapping(body.get("agent"), field_name="agent")
            created_payload = None
            if self._agent_create_handler is not None:
                created_payload = await _maybe_await(self._agent_create_handler(agent_payload))
            await self.send_json(
                "agent.created",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "agent": dict(created_payload) if isinstance(created_payload, Mapping) else {},
                },
            )
            return
        if message_type == "node.capabilities.resolve":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            await self.send_json(
                "node.capabilities",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "capabilities": build_runtime_capabilities().as_payload(),
                },
            )
            return
        if message_type == "agent.capabilities.resolve":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            agent_id = _require_text(body.get("agent_id"), field_name="agent_id")
            workspace_root = _require_text(body.get("workspace_root"), field_name="workspace_root")
            capability_payload = None
            if self._agent_capabilities_provider is not None:
                capability_payload = await _maybe_await(self._agent_capabilities_provider(agent_id, workspace_root))
            await self.send_json(
                "agent.capabilities",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "agent_id": agent_id,
                    "workspace_root": workspace_root,
                    "capabilities": dict(capability_payload) if isinstance(capability_payload, Mapping) else {},
                },
            )
            return
        if message_type == "node.streaming_delta":
            # IM → PA direction: currently only permission_response kind is routed here.
            # Other kinds (turn_start, message_delta, …) are PA→IM only and would be
            # unexpected inbound; they are safely ignored.
            kind = body.get("kind")
            if kind == "permission_response" and self._permission_response_handler is not None:
                self._permission_response_handler(body)
            return
        raise ValueError(f"unsupported downstream message type: {message_type}")

    async def _flush_pending_frames(self, *, raise_on_disconnect: bool = False) -> None:
        async with self._flush_lock:
            if self._awaiting_ack_type is not None or not self._pending_frames:
                return
            pending_frame = self._pending_frames[0]
            try:
                await self._send_frame(pending_frame.message_type, pending_frame.payload)
            except Exception as exc:  # noqa: BLE001
                await self._disconnect_current_websocket(exc)
                if raise_on_disconnect:
                    raise
                return
            self._awaiting_ack_type = pending_frame.message_type

    async def _send_frame(self, message_type: str, payload: Mapping[str, object]) -> None:
        websocket = self._require_websocket()
        frame = json.dumps({"type": message_type, "payload": dict(payload)}, ensure_ascii=False)
        await websocket.send(frame)
        self._events.append({"event": "sent", "type": message_type})

    async def _disconnect_current_websocket(self, exc: Exception | None = None) -> None:
        websocket = self._websocket
        heartbeat_task = self._heartbeat_task
        self._mark_disconnected(exc)
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:  # noqa: BLE001
                return
        if heartbeat_task is not None and heartbeat_task is not asyncio.current_task():
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

    def _ack_pending_frame(self, payload: Mapping[str, object]) -> None:
        awaiting = self._awaiting_ack_type
        if awaiting is None:
            return
        ack_type = payload.get("message_type")
        if not isinstance(ack_type, str) or ack_type.strip() != awaiting:
            return
        pending_frame = self._pending_frames.popleft()
        self._awaiting_ack_type = None
        if pending_frame.ack_future is not None and not pending_frame.ack_future.done():
            pending_frame.ack_future.set_result(dict(payload))
        self._events.append({"event": "acked", "type": awaiting})

    def _start_heartbeat_loop(self) -> None:
        interval = self._config.normalized_heartbeat_interval_seconds()
        if interval is None:
            return
        existing = self._heartbeat_task
        if existing is not None and not existing.done():
            return
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(interval), name="personal-assistant-im-heartbeat")

    def _stop_heartbeat_loop(self) -> None:
        task = self._heartbeat_task
        self._heartbeat_task = None
        if task is not None:
            task.cancel()

    async def _heartbeat_loop(self, interval_seconds: float) -> None:
        try:
            while self._connected and not self._stop_requested:
                await self._sleep(interval_seconds)
                if not self._connected or self._stop_requested:
                    break
                try:
                    await self._send_frame("node.heartbeat", self._reporter.send_heartbeat(status="online"))
                except Exception as exc:  # noqa: BLE001
                    await self._disconnect_current_websocket(exc)
                    return
        except asyncio.CancelledError:
            raise

    def _mark_disconnected(self, exc: Exception | None = None) -> None:
        had_connection = self._connected or self._websocket is not None
        pending_frame = self._pending_frames[0] if self._pending_frames else None
        self._connected = False
        self._websocket = None
        self._awaiting_ack_type = None
        self._stop_heartbeat_loop()
        if pending_frame is not None and pending_frame.ack_future is not None and not pending_frame.ack_future.done():
            pending_frame.ack_future.set_exception(RuntimeError("IM websocket disconnected before ack"))
        if had_connection:
            event: dict[str, object] = {"event": "disconnected"}
            if exc is not None:
                event["error"] = str(exc)
            self._events.append(event)

    def _require_websocket(self) -> ClientWebSocket:
        websocket = self._websocket
        if websocket is None:
            raise RuntimeError("IM websocket is not connected")
        return websocket


async def _maybe_await(value: Awaitable[Mapping[str, object] | None] | Mapping[str, object] | None) -> Mapping[str, object] | None:
    if asyncio.iscoroutine(value) or isinstance(value, Awaitable):
        return await value
    return value


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


def _require_mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value
