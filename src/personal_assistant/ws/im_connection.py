"""Gateway-side IM websocket client with reconnect/backoff and downstream dispatch."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol
from urllib.parse import urlparse

from personal_assistant._utils import _require_text
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.gateway.managed_channel_control import (
    ChannelRuntimeMetadataEmission,
    ChannelStatusDirective,
    ChannelStatusEmission,
    ManagedChannelBindings,
    ManagedChannelEmission,
    ManagedChannelConnectionSender,
)
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.defaults import (
    WORKSPACE_CONFIG_DIRNAME as _PA_WORKSPACE_CFG_DIR,
)
from personal_assistant.reporter.upstream_reporter import UpstreamReporter

_log = logging.getLogger("personal_assistant.ws.im_connection")


_PA_SHARED_SKILL_ROOTS: tuple[Path, ...] = (
    Path("~/.nanoassistant/skills"),
    Path("~/.claude/skills"),
    Path("~/.codex/skills"),
)


class _RegistrationAckDeadlineExpired(TimeoutError):
    """Signal that no downstream frame arrived before the registration deadline."""


@dataclass(slots=True)
class PendingFrame:
    """Track one unsent upstream frame plus its optional ack waiter."""

    message_type: str
    payload: dict[str, object]
    ack_future: asyncio.Future[dict[str, object]] | None = field(
        default=None, repr=False
    )
    send_completed: asyncio.Event | None = field(default=None, repr=False)
    requeue_on_disconnect: bool = True


@dataclass(slots=True)
class WireFrameOwner:
    """Own the one control or business frame crossing or awaiting the wire."""

    frame: PendingFrame
    lane: Literal["control", "business"]
    phase: Literal["sending", "awaiting_result"]


class IMFrameRejectedError(RuntimeError):
    """Report one IM-rejected outbound frame to its owning caller."""

    def __init__(self, message: str, *, code: str = "protocol_error") -> None:
        super().__init__(message)
        self.code = code


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
            conversation_id=_require_text(
                payload.get("conversation_id"), field_name="conversation_id"
            ),
            message_id=_require_text(
                payload.get("message_id"), field_name="message_id"
            ),
            target_kind=_require_text(
                payload.get("target_kind"), field_name="target_kind"
            ),
            target_id=_require_text(payload.get("target_id"), field_name="target_id"),
            source_agent_id=_require_text(
                payload.get("source_agent_id"), field_name="source_agent_id"
            ),
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
AgentCreateHandler = Callable[
    [Mapping[str, object]],
    Awaitable[Mapping[str, object] | None] | Mapping[str, object] | None,
]
AgentConfigOperationHandler = Callable[
    [str, Mapping[str, object]],
    Awaitable[Mapping[str, object]] | Mapping[str, object],
]
NodePromptWorkspaceResolver = Callable[[str, str | None, str | None], str]
AgentCapabilitiesProvider = Callable[
    [str, str], Awaitable[Mapping[str, object] | None] | Mapping[str, object] | None
]
# refactor-406-M2: node.capabilities payload is now built by a Gateway projection
# that holds the in-process Kernel (decision 4); injected as a provider instead of
# importing a module-level builder, so the WS layer stays kernel-agnostic.
NodeCapabilitiesProvider = Callable[[], Mapping[str, object]]
# feat-379-M2 R5: (agent_id, workspace_root, features, custom_prompt, tool_ids, scenario, skill_ids) → preview dict | None
# feat-383-M1: added skill_ids parameter so kernel can resolve real skill descriptions
PromptPreviewProvider = Callable[
    [str, str, dict, "str | None", list, str, list],
    "Awaitable[Mapping[str, object] | None] | Mapping[str, object] | None",
]
# Async callback that returns a fresh access token immediately before each connect attempt.
# Returning None means "no token available"; the caller should fall back or proceed without auth.
TokenGetter = Callable[[], Awaitable[str | None]]
# Called when IM sends a node.streaming_delta kind=permission_response.
# Payload keys: request_id, decision, message_id.  PA should POST the decision
# to the agent inbound endpoint to unpark the auto_mode_gate hook.
PermissionResponseHandler = Callable[[Mapping[str, object]], bool | None]
# feat-445-M1: IM delegates session fork over WS. Given the fork request payload
# (source_conversation_id / new_conversation_id / agent_id / fork_point.message_id),
# the gateway-side handler locates the source kernel session, forks it at the point,
# binds the new conversation, and returns {ok, new_session_id?, error?}.
SessionForkHandler = Callable[
    [Mapping[str, object]],
    Awaitable[Mapping[str, object]] | Mapping[str, object],
]
# Gateway resolves local durable bindings into the existing distill prompt.  The
# request contains identities only; its result carries either prompt or error.
DistillPromptHandler = Callable[
    [Mapping[str, object]],
    Awaitable[Mapping[str, object]] | Mapping[str, object],
]
# Provides encrypted managed-channel items for a newly bound IM. The IM owner id
# is needed to re-seal a cache that was associated with a different IM instance.
ChannelBootstrapItemsProvider = Callable[[str], list[Mapping[str, object]]]


def build_permission_response_handler(
    *, kernel: Any
) -> Callable[[Mapping[str, object]], bool]:
    """Build the WS permission-decision handler for the in-process Kernel."""

    def handle(body: Mapping[str, object]) -> bool:
        request_id = str(body.get("request_id") or "").strip()
        decision = str(body.get("decision") or "").strip()
        if not request_id or not decision:
            return False
        try:
            return bool(
                kernel.submit_permission_decision(
                    request_id=request_id,
                    decision=decision,
                    reason=str(body.get("reason") or "").strip(),
                )
            )
        except Exception:  # noqa: BLE001
            return False

    return handle


@dataclass(frozen=True, slots=True)
class IMConnectionConfig:
    """Configure IM websocket connectivity and reconnect behavior.

    Args:
        url: IM service base URL or websocket URL.
        token: Optional bearer token for upstream auth.
        reconnect_initial_seconds: Initial reconnect delay after failure.
        reconnect_max_seconds: Maximum reconnect delay cap.
        heartbeat_interval_seconds: Delay between periodic node heartbeats while connected.
        heartbeat_ack_timeout_seconds: Maximum total wait to send one heartbeat and
            receive its IM acknowledgment.
        registration_ack_timeout_seconds: Maximum total wait to send node
            registration and receive its acknowledgment after transport connects.
        business_ack_timeout_seconds: Maximum time one business frame may own the
            wire while sending or awaiting its acknowledgment.
    """

    url: str
    token: str | None = None
    reconnect_initial_seconds: float = 1.0
    reconnect_max_seconds: float = 60.0
    heartbeat_interval_seconds: float = 30.0
    heartbeat_ack_timeout_seconds: float = 10.0
    registration_ack_timeout_seconds: float = 10.0
    business_ack_timeout_seconds: float = 10.0

    def normalized_heartbeat_interval_seconds(self) -> float | None:
        interval = self.heartbeat_interval_seconds
        if interval <= 0:
            return None
        return interval

    def normalized_heartbeat_ack_timeout_seconds(self) -> float | None:
        timeout = self.heartbeat_ack_timeout_seconds
        if timeout <= 0:
            return None
        return timeout

    def normalized_registration_ack_timeout_seconds(self) -> float | None:
        timeout = self.registration_ack_timeout_seconds
        if timeout <= 0:
            return None
        return timeout

    def normalized_business_ack_timeout_seconds(self) -> float | None:
        """Return the configured business-frame liveness budget."""

        timeout = self.business_ack_timeout_seconds
        if timeout <= 0:
            return None
        return timeout

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
        channel_bootstrap_items_provider: Optional encrypted cache exporter used when a
            newly bound IM requests managed-channel initialization.
        connect: Async websocket connector implementation.
        sleep: Async sleep implementation used for reconnect backoff.

    Notes:
        When the socket drops, this manager only updates local state and retries later.
        It does not interrupt the gateway's local IM/channel execution path, preserving
        the gateway local-autonomy requirement (see docs/specs/gateway/spec.md).
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
        agent_config_operation_handler: AgentConfigOperationHandler | None = None,
        agent_capabilities_provider: AgentCapabilitiesProvider | None = None,
        node_capabilities_provider: NodeCapabilitiesProvider | None = None,
        prompt_preview_provider: PromptPreviewProvider | None = None,
        node_prompt_workspace_resolver: NodePromptWorkspaceResolver | None = None,
        session_fork_handler: SessionForkHandler | None = None,
        distill_prompt_handler: DistillPromptHandler | None = None,
        token_getter: TokenGetter | None = None,
        permission_response_handler: PermissionResponseHandler | None = None,
        on_connected: Callable[[ManagedChannelConnectionSender], Awaitable[None]]
        | None = None,
        managed_channel_bindings: ManagedChannelBindings | None = None,
        channel_bootstrap_items_provider: ChannelBootstrapItemsProvider | None = None,
        channel_reconcile_retry_delays: tuple[float, ...] = (0.5, 1.0, 2.0),
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
        self._agent_config_operation_handler = agent_config_operation_handler
        self._agent_capabilities_provider = agent_capabilities_provider
        self._node_capabilities_provider = node_capabilities_provider
        # feat-379-M2 R5: provider for prompt preview; calls agent HTTP /v1/prompt-preview.
        self._prompt_preview_provider = prompt_preview_provider
        self._node_prompt_workspace_resolver = node_prompt_workspace_resolver
        # feat-445-M1: handler for IM-delegated session fork (decision 2).
        self._session_fork_handler = session_fork_handler
        self._distill_prompt_handler = distill_prompt_handler
        # Called when IM pushes a permission_response so PA can POST it to the agent.
        self._permission_response_handler = permission_response_handler
        # token_getter is called on each connect attempt to supply a fresh access token.
        # When absent the static config.token is used (backwards-compatible behaviour).
        self._token_getter = token_getter
        # feat-394-M12 决策 F: async callback invoked after each successful WS bind
        # (node.register ack received). Used to trigger reconcile_all_agents so gateway
        # config converges to IM truth on connect and every reconnect.
        self._on_connected = on_connected
        self._managed_channel_bindings = managed_channel_bindings
        self._channel_bootstrap_items_provider = channel_bootstrap_items_provider
        if managed_channel_bindings is not None:
            managed_channel_bindings.emissions.bind_sender(self._send_managed_emission)
        self._channel_reconcile_retry_delays = channel_reconcile_retry_delays
        self._connect = connect
        self._sleep = sleep
        self._websocket: ClientWebSocket | None = None
        self._connected = False
        self._stop_requested = False
        self._reconnect_delay = config.reconnect_initial_seconds
        self._events: list[dict[str, object]] = []
        self._pending_control_frames: deque[PendingFrame] = deque()
        self._pending_frames: deque[PendingFrame] = deque()
        self._external_shadow_run_ids: set[str] = set()
        self._wire_frame_owner: WireFrameOwner | None = None
        self._registered = False
        self._connection_epoch = 0
        self._registration_deadline: float | None = None
        self._outbound_drained: asyncio.Event | None = None
        self._flush_lock = asyncio.Lock()
        self._business_ack_timeout_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._heartbeat_ack_future: asyncio.Future[dict[str, object]] | None = None
        self._stop_event: asyncio.Event | None = None
        # bugfix-446-M1 (decision 3 guard): set after the first connect attempt resolves
        # (success OR failure). Heartbeat startup waits on this so the first tick never
        # fires before the initial handshake has had a chance to complete — without it,
        # removing the eager connect_once would regress feat-393 (the delivery observer
        # silently drops while not connected).  Lazily created so it binds to the loop
        # that actually runs run_forever.
        self._first_connect_resolved: asyncio.Event | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._latest_channel_manifest_revision = 0
        self._channel_manifest_retry_task: asyncio.Task[None] | None = None

    @property
    def connected(self) -> bool:
        """Report whether the IM websocket is currently connected."""

        return self._connected

    @property
    def _awaiting_ack_type(self) -> str | None:
        """Expose the derived wire response owner for focused protocol tests."""
        owner = self._wire_frame_owner
        if owner is None or owner.phase != "awaiting_result":
            return None
        return owner.frame.message_type

    def event_log(self) -> tuple[dict[str, object], ...]:
        """Return an immutable snapshot of connection lifecycle events."""

        return tuple(self._events)

    async def connect_once(self) -> None:
        """Open the IM websocket, register the node, and flush buffered upstream frames.

        When ``token_getter`` is provided it is called before every connect attempt so
        each reconnect uses a freshly minted access token rather than the stale value
        that was loaded at startup.
        """

        self._event_loop = asyncio.get_running_loop()
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
        registration_timeout = (
            self._config.normalized_registration_ack_timeout_seconds()
        )
        self._registration_deadline = (
            self._event_loop.time() + registration_timeout
            if registration_timeout is not None
            else None
        )
        self._events.append({"event": "connected", "url": self._config.websocket_url()})
        try:
            self._outbound_drained_event().clear()
            self._pending_control_frames.append(
                PendingFrame(
                    message_type="node.register",
                    payload=dict(self._reporter.send_register()),
                )
            )
            if registration_timeout is None:
                await self._flush_pending_frames(raise_on_disconnect=True)
            else:
                try:
                    async with asyncio.timeout(registration_timeout):
                        await self._flush_pending_frames(
                            raise_on_disconnect=True,
                            disconnect_on_cancel=False,
                        )
                except TimeoutError as exc:
                    raise TimeoutError(
                        "IM node.register send timed out after "
                        f"{registration_timeout:.2f}s"
                    ) from exc
        except Exception as exc:  # noqa: BLE001
            await self._disconnect_current_websocket(exc)
            raise

    async def close(self) -> None:
        """Stop reconnect attempts and close the current websocket if present."""

        self._stop_requested = True
        stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()
        heartbeat_task = self._heartbeat_task
        retry_task = self._channel_manifest_retry_task
        self._channel_manifest_retry_task = None
        if retry_task is not None:
            retry_task.cancel()
        self._stop_heartbeat_loop()
        self._stop_business_ack_timeout()
        websocket = self._websocket
        self._websocket = None
        self._connected = False
        self._registered = False
        self._registration_deadline = None
        if websocket is not None:
            await websocket.close()
        if heartbeat_task is not None and heartbeat_task is not asyncio.current_task():
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task
        if retry_task is not None and retry_task is not asyncio.current_task():
            with contextlib.suppress(asyncio.CancelledError):
                await retry_task
        self._events.append({"event": "closed"})

    async def drain(self, deadline: float) -> None:
        """Wait until every queued outbound frame has been acknowledged by IM.

        Args:
            deadline: Absolute event-loop deadline shared by Gateway shutdown.

        Raises:
            TimeoutError: When IM does not acknowledge all queued frames in time.
        """

        drained = self._outbound_drained_event()
        self._mark_outbound_drained_if_idle()
        try:
            async with asyncio.timeout_at(deadline):
                await drained.wait()
        except TimeoutError:
            owner = self._wire_frame_owner
            queued = [frame.message_type for frame in self._pending_control_frames]
            if owner is not None:
                queued.append(owner.frame.message_type)
            queued.extend(frame.message_type for frame in self._pending_frames)
            raise TimeoutError(
                f"IM outbound frames exceeded shutdown deadline: {queued}"
            ) from None

    async def send_json(self, message_type: str, payload: Mapping[str, object]) -> None:
        """Queue one gateway -> IM protocol frame and flush it when the socket is available."""

        self._queue_pending_frame(
            PendingFrame(message_type=message_type, payload=dict(payload))
        )
        await self._flush_pending_frames()

    def send_json_threadsafe(
        self, message_type: str, payload: Mapping[str, object]
    ) -> bool:
        """Queue one worker-thread status/metadata frame on the bound Gateway loop."""
        loop = self._event_loop
        if loop is None or loop.is_closed() or not loop.is_running():
            return False
        asyncio.run_coroutine_threadsafe(self.send_json(message_type, payload), loop)
        return True

    def _send_managed_emission(self, emission: ManagedChannelEmission) -> None:
        """Schedule one typed control emission on its current registered socket only."""

        loop = self._event_loop
        if (
            loop is None
            or loop.is_closed()
            or not loop.is_running()
            or not self._connected
            or not self._registered
        ):
            return
        connection_epoch = self._connection_epoch
        asyncio.run_coroutine_threadsafe(
            self._queue_managed_emission(emission, connection_epoch), loop
        )

    async def _queue_managed_emission(
        self, emission: ManagedChannelEmission, connection_epoch: int
    ) -> None:
        """Project one live provider emission only while its socket stays registered."""

        if (
            not self._connected
            or not self._registered
            or connection_epoch != self._connection_epoch
        ):
            return
        if isinstance(emission, ChannelStatusEmission):
            message_type = "channel.status"
        elif isinstance(emission, ChannelRuntimeMetadataEmission):
            message_type = "channel.runtime_metadata"
        else:
            raise TypeError(f"unsupported managed channel emission: {type(emission)!r}")
        request_id = emission.payload.get("request_id")
        if (
            isinstance(emission, ChannelStatusEmission)
            and isinstance(request_id, str)
            and self.has_pending_request(request_id)
        ):
            return
        await self.send_json(message_type, emission.payload)

    def has_pending_request(self, request_id: str) -> bool:
        """Return whether one correlated request is already queued or in flight."""
        owner = self._wire_frame_owner
        return (
            owner is not None
            and owner.lane == "business"
            and owner.frame.payload.get("request_id") == request_id
        ) or any(
            frame.payload.get("request_id") == request_id
            for frame in self._pending_frames
        )

    async def send_json_await_ack(
        self, message_type: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        """Queue one frame and wait until the matching ack payload arrives."""

        loop = asyncio.get_running_loop()
        ack_future: asyncio.Future[dict[str, object]] = loop.create_future()
        send_completed = asyncio.Event()
        self._queue_pending_frame(
            PendingFrame(
                message_type=message_type,
                payload=dict(payload),
                ack_future=ack_future,
                send_completed=send_completed,
            )
        )
        try:
            await self._flush_pending_frames()
            # A frame queued behind another business owner has not consumed any of its
            # own ACK budget yet. Its ACK timer begins after its send completes.
            await send_completed.wait()
            return await asyncio.shield(ack_future)
        finally:
            if not ack_future.done():
                ack_future.cancel()
            elif not ack_future.cancelled():
                ack_future.exception()

    def _queue_pending_frame(self, pending: PendingFrame) -> None:
        """Append a frame, coalescing only statuses still owned by the pending queue.

        The wire owner is transferred out of this queue before ``websocket.send`` may
        yield.  Coalescing therefore cannot delete a frame whose send has begun.
        """
        self._classify_external_shadow_frame(pending)
        if not pending.requeue_on_disconnect and (
            not self._connected or not self._registered
        ):
            self._fail_pending_frame(
                pending,
                RuntimeError(
                    "external shadow live frame dropped while IM websocket is offline"
                ),
            )
            return
        self._outbound_drained_event().clear()
        if pending.message_type != "channel.status":
            self._pending_frames.append(pending)
            return
        channel_id = pending.payload.get("channel_id")
        incarnation = pending.payload.get("runtime_incarnation")
        if not isinstance(channel_id, str) or not isinstance(incarnation, str):
            self._pending_frames.append(pending)
            return

        status_sequence = pending.payload.get("status_sequence")
        retained: deque[PendingFrame] = deque()
        for queued in self._pending_frames:
            same_channel = (
                queued.message_type == "channel.status"
                and queued.payload.get("channel_id") == channel_id
            )
            if not same_channel or queued.ack_future is not None:
                retained.append(queued)
                continue
            queued_incarnation = queued.payload.get("runtime_incarnation")
            queued_sequence = queued.payload.get("status_sequence")
            keep_barrier = (
                queued_incarnation == incarnation
                and queued_sequence == 1
                and isinstance(status_sequence, int)
                and status_sequence > 1
            )
            if keep_barrier:
                retained.append(queued)
        retained.append(pending)
        self._pending_frames = retained

    def _is_status_superseded_by_pending(self, frame: PendingFrame) -> bool:
        if frame.message_type != "channel.status":
            return False
        channel_id = frame.payload.get("channel_id")
        incarnation = frame.payload.get("runtime_incarnation")
        if not isinstance(channel_id, str) or not isinstance(incarnation, str):
            return False
        return any(
            pending.message_type == "channel.status"
            and pending.payload.get("channel_id") == channel_id
            and pending.payload.get("runtime_incarnation") != incarnation
            for pending in self._pending_frames
        )

    async def send_agent_message(self, payload: Mapping[str, object]) -> IMDispatchAck:
        """Send one agent.message frame and return the parsed IM dispatch ack."""

        ack_payload = await self.send_json_await_ack("agent.message", payload)
        return IMDispatchAck.from_payload(ack_payload)

    def _first_attempt_event(self) -> asyncio.Event:
        # Lazily created so it binds to whichever loop runs run_forever / the waiter.
        if self._first_connect_resolved is None:
            self._first_connect_resolved = asyncio.Event()
        return self._first_connect_resolved

    def _outbound_drained_event(self) -> asyncio.Event:
        event = self._outbound_drained
        if event is None:
            event = asyncio.Event()
            self._outbound_drained = event
        return event

    def _mark_outbound_drained_if_idle(self) -> None:
        if (
            self._wire_frame_owner is None
            and not self._pending_control_frames
            and not self._pending_frames
        ):
            self._outbound_drained_event().set()

    def _stop_wait_event(self) -> asyncio.Event:
        if self._stop_event is None:
            self._stop_event = asyncio.Event()
        if self._stop_requested:
            self._stop_event.set()
        return self._stop_event

    async def wait_first_connect_attempt(self, *, timeout: float = 10.0) -> None:
        """Block until the first connect attempt has resolved (success or failure).

        Heartbeat startup waits on this so the first tick never fires before the
        initial handshake has had a chance to complete (bugfix-446-M1 decision 3
        guard). Bounded by ``timeout`` so a hung connect never blocks startup
        forever; on timeout it returns rather than raising — the caller then
        proceeds and heartbeat delivery simply observes the not-connected state,
        which is correct when IM is genuinely unreachable.
        """

        event = self._first_attempt_event()
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            _log.warning(
                "first IM connect attempt did not resolve within %.2fs; continuing startup",
                timeout,
            )
            return

    async def run_forever(self) -> None:
        """Maintain the IM websocket until ``close`` is requested.

        Exception boundary (bugfix-446-M1 decision 2):
        - ``CancelledError`` runs disconnect cleanup then re-raises, honoring task
          cancellation (issue path 5: the old ``except Exception`` skipped cleanup).
        - ``Exception`` is a transient fault: clean up and retry with exponential
          backoff.
        - Any other ``BaseException`` propagates to the outer watchdog (main.py
          supervisor), which rebuilds this loop — strong-swallowing
          KeyboardInterrupt/SystemExit here would break process shutdown.
        """

        first_attempt = self._first_attempt_event()
        while not self._stop_requested:
            try:
                if not self._connected:
                    await self.connect_once()
                    first_attempt.set()
                if not self._registered:
                    await self._await_registration()
                else:
                    await self._listen_once()
                if not self._connected:
                    # Control-frame rejection closes the socket inside the frame
                    # handler. Treat that normal return as a connection failure so
                    # it shares the same bounded backoff as recv/connect failures.
                    raise ConnectionError(
                        "IM websocket disconnected while handling a control frame"
                    )
            except asyncio.CancelledError:
                first_attempt.set()
                await self._disconnect_current_websocket()
                raise
            except Exception as exc:  # noqa: BLE001
                first_attempt.set()
                await self._disconnect_current_websocket(exc)
                if self._stop_requested:
                    break
                if await self._sleep_until_stop(self._reconnect_delay):
                    break
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._config.reconnect_max_seconds
                )
            finally:
                first_attempt.set()

    async def _await_registration(self) -> None:
        """Process downstream frames until IM accepts this websocket identity."""
        timeout = self._config.normalized_registration_ack_timeout_seconds()
        if timeout is None:
            while self._connected and not self._registered:
                await self._listen_once()
            return

        deadline = self._registration_deadline
        if deadline is None:
            deadline = asyncio.get_running_loop().time() + timeout
        try:
            while self._connected and not self._registered:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise _RegistrationAckDeadlineExpired
                await self._listen_once(receive_timeout_seconds=remaining)
        except _RegistrationAckDeadlineExpired as exc:
            raise TimeoutError(
                f"IM node.register ack timed out after {timeout:.2f}s"
            ) from exc

    async def _sleep_until_stop(self, delay: float) -> bool:
        if self._stop_requested:
            return True
        sleep_task = asyncio.create_task(self._sleep(delay))
        stop_task = asyncio.create_task(self._stop_wait_event().wait())
        done, pending = await asyncio.wait(
            {sleep_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if sleep_task in done:
            await sleep_task
        return self._stop_requested or stop_task in done

    async def _apply_channel_manifest_and_send(
        self,
        *,
        body: Mapping[str, object],
        request_id: str,
        supersede_retry: bool = True,
    ) -> dict[str, object]:
        bindings = self._managed_channel_bindings
        if bindings is None:
            raise RuntimeError("channel.reconcile requires managed_channel_bindings")
        revision = int(body.get("manifest_revision") or 0)
        if supersede_retry and revision >= self._latest_channel_manifest_revision:
            self._latest_channel_manifest_revision = revision
            retry_task = self._channel_manifest_retry_task
            if retry_task is not None and retry_task is not asyncio.current_task():
                retry_task.cancel()
            self._channel_manifest_retry_task = None
        result = await bindings.apply_manifest(body)
        result_payload = dict(result) if isinstance(result, Mapping) else {}
        await self.send_json(
            "channel.reconcile.result",
            {
                "request_id": request_id,
                "node_id": self._reporter.node_id,
                "manifest_revision": revision,
                **result_payload,
            },
        )
        return result_payload

    def _schedule_channel_manifest_retry(
        self,
        *,
        body: Mapping[str, object],
        request_id: str,
        result_payload: Mapping[str, object],
    ) -> None:
        if result_payload.get("outcome") != "retryable_failed":
            return
        revision = int(body.get("manifest_revision") or 0)
        if revision != self._latest_channel_manifest_revision:
            return
        task = asyncio.create_task(
            self._retry_channel_manifest(
                body=dict(body),
                request_id=request_id,
                manifest_revision=revision,
            ),
            name=f"channel-manifest-retry:{revision}",
        )
        self._channel_manifest_retry_task = task
        task.add_done_callback(self._channel_manifest_retry_done)

    async def _retry_channel_manifest(
        self,
        *,
        body: Mapping[str, object],
        request_id: str,
        manifest_revision: int,
    ) -> None:
        for attempt, delay in enumerate(self._channel_reconcile_retry_delays, start=1):
            await self._sleep(delay)
            if (
                self._stop_requested
                or manifest_revision != self._latest_channel_manifest_revision
            ):
                return
            result = await self._apply_channel_manifest_and_send(
                body=body,
                request_id=f"{request_id}:retry:{attempt}",
                supersede_retry=False,
            )
            if result.get("outcome") != "retryable_failed":
                return

    def _channel_manifest_retry_done(self, task: asyncio.Task[None]) -> None:
        if self._channel_manifest_retry_task is task:
            self._channel_manifest_retry_task = None
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            _log.warning("channel manifest retry failed", exc_info=True)

    async def _listen_once(
        self, *, receive_timeout_seconds: float | None = None
    ) -> None:
        websocket = self._require_websocket()
        if receive_timeout_seconds is None:
            raw = await websocket.recv()
        else:
            try:
                async with asyncio.timeout(receive_timeout_seconds):
                    raw = await websocket.recv()
            except TimeoutError as exc:
                raise _RegistrationAckDeadlineExpired from exc
        payload = _decode_message(raw)
        message_type = _require_text(payload.get("type"), field_name="type")
        body = payload.get("payload")
        if body is None:
            body = {}
        if not isinstance(body, Mapping):
            raise ValueError("payload must be an object")
        self._events.append({"event": "frame", "type": message_type})
        if message_type == "ack":
            released = self._ack_pending_frame(body)
            if released is not None and released.message_type == "node.register":
                self._registered = True
                self._registration_deadline = None
                self._reconnect_delay = self._config.reconnect_initial_seconds
                await self._notify_registered()
                # on_connected runs inside the receive owner after register ACK.
                # Starting heartbeat earlier would send an ACK-gated control frame
                # while this callback prevents the receive owner from consuming it.
                self._start_heartbeat_loop()
            await self._flush_pending_frames()
            return
        if message_type == "relay.message":
            self._relay_adapter.accept_relay(body)
            return
        if message_type == "config.sync":
            if self._sync_client is not None:
                self._sync_client.handle_notification(body)
            return
        if message_type == "channel.reconcile":
            if self._managed_channel_bindings is None:
                raise RuntimeError(
                    "channel.reconcile requires managed_channel_bindings"
                )
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            result_payload = await self._apply_channel_manifest_and_send(
                body=body, request_id=request_id
            )
            self._schedule_channel_manifest_retry(
                body=body,
                request_id=request_id,
                result_payload=result_payload,
            )
            return
        if message_type == "channels.bootstrap.request":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            owner_id = _require_text(body.get("owner_id"), field_name="owner_id")
            provider = self._channel_bootstrap_items_provider
            items = provider(owner_id) if provider is not None else []
            await self.send_json(
                "channels.bootstrap",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "items": items,
                },
            )
            return
        if message_type == "channels.bootstrap.result":
            self._resolve_correlated_channel_result(
                message_type=message_type, payload=body
            )
            manifest = body.get("manifest")
            if not isinstance(manifest, Mapping):
                raise ValueError("channels.bootstrap.result manifest is required")
            bindings = self._managed_channel_bindings
            if bindings is None:
                raise RuntimeError(
                    "channels.bootstrap.result requires managed_channel_bindings"
                )
            result = await bindings.apply_manifest(manifest)
            result_payload = dict(result) if isinstance(result, Mapping) else {}
            await self.send_json(
                "channel.reconcile.result",
                {
                    "request_id": _require_text(
                        manifest.get("request_id"), field_name="request_id"
                    ),
                    "node_id": self._reporter.node_id,
                    "manifest_revision": int(manifest.get("manifest_revision") or 0),
                    **result_payload,
                },
            )
            return
        if message_type == "channel.reconnect":
            bindings = self._managed_channel_bindings
            if bindings is None:
                raise RuntimeError(
                    "channel.reconnect requires managed_channel_bindings"
                )
            channel_id = _require_text(body.get("channel_id"), field_name="channel_id")
            revision = int(body.get("channel_revision") or 0)
            await bindings.reconnect(channel_id, revision)
            return
        if message_type in {
            "channel.status.result",
            "channel.runtime_metadata.result",
            "channels.reconcile.result.ack",
        }:
            resolved = self._resolve_correlated_channel_result(
                message_type=message_type, payload=body
            )
            bindings = self._managed_channel_bindings
            if (
                resolved
                and message_type == "channel.status.result"
                and bindings is not None
            ):
                directive = await bindings.handle_status_result(body)
                if directive == ChannelStatusDirective.CLOSE_CONNECTION:
                    await self.close()
                    return
            if message_type == "channels.reconcile.result.ack" and bindings is not None:
                bindings.acknowledge_reconcile(body)
            if self._connected:
                await self._flush_pending_frames()
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
            if (
                body.get("operation_id") is not None
                and self._agent_config_operation_handler is not None
            ):
                created_payload = await _maybe_await(
                    self._agent_config_operation_handler("create", body)
                )
            elif self._agent_create_handler is not None:
                created_payload = await _maybe_await(
                    self._agent_create_handler(agent_payload)
                )
            response_payload: dict[str, object] = {
                "request_id": request_id,
                "node_id": self._reporter.node_id,
            }
            if body.get("operation_id") is not None:
                response_payload.update(
                    dict(created_payload)
                    if isinstance(created_payload, Mapping)
                    else {}
                )
            else:
                created_error = (
                    created_payload.get("error")
                    if isinstance(created_payload, Mapping)
                    else None
                )
                response_payload["agent"] = (
                    {}
                    if isinstance(created_error, Mapping)
                    else dict(created_payload)
                    if isinstance(created_payload, Mapping)
                    else {}
                )
                if isinstance(created_error, Mapping):
                    response_payload["error"] = dict(created_error)
            await self.send_json(
                "agent.created",
                response_payload,
            )
            return
        if message_type == "agent.config.apply":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            if self._agent_config_operation_handler is None:
                raise RuntimeError(
                    "agent.config.apply requires agent_config_operation_handler"
                )
            result = await _maybe_await(
                self._agent_config_operation_handler("apply", body)
            )
            await self.send_json(
                "agent.config.apply.result",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    **dict(result),
                },
            )
            return
        if message_type == "agent.config.operation.status":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            if self._agent_config_operation_handler is None:
                raise RuntimeError(
                    "agent.config.operation.status requires "
                    "agent_config_operation_handler"
                )
            result = await _maybe_await(
                self._agent_config_operation_handler("status", body)
            )
            await self.send_json(
                "agent.config.operation.status.result",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    **dict(result),
                },
            )
            return
        if message_type == "session.fork.request":
            # feat-445-M1 (decision 2): IM delegates the session fork. The handler locates
            # the source kernel session via its binding, forks it at fork_point, binds the
            # new conversation, and reports back. A missing handler is a wiring bug — fail
            # loud rather than silently never answering (IM would block on the waiter).
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            if self._session_fork_handler is None:
                raise RuntimeError("session.fork.request requires session_fork_handler")
            result = await _maybe_await(self._session_fork_handler(body))
            result_payload = dict(result) if isinstance(result, Mapping) else {}
            await self.send_json(
                "session.fork.result",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    **result_payload,
                },
            )
            return
        if message_type == "node.distill.prompt.request":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            if self._distill_prompt_handler is None:
                raise RuntimeError(
                    "node.distill.prompt.request requires distill_prompt_handler"
                )
            result = await _maybe_await(self._distill_prompt_handler(body))
            result_payload = dict(result) if isinstance(result, Mapping) else {}
            await self.send_json(
                "node.distill.prompt",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    **result_payload,
                },
            )
            return
        if message_type == "node.capabilities.resolve":
            # feat-379-M7 (ISSUE-1): node-level capability payload carries the feature
            # projection so the agent-create page can render feature toggles (no
            # per-agent context yet → all features available=True at node level).
            # refactor-406-M2: built by the injected provider (holds the Kernel for
            # decision-4 list_* queries) instead of a module-level builder.
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            if self._node_capabilities_provider is None:
                raise RuntimeError(
                    "node.capabilities.resolve requires node_capabilities_provider"
                )
            await self.send_json(
                "node.capabilities",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "capabilities": dict(self._node_capabilities_provider()),
                },
            )
            return
        if message_type == "agent.capabilities.resolve":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            agent_id = _require_text(body.get("agent_id"), field_name="agent_id")
            workspace_root = _require_text(
                body.get("workspace_root"), field_name="workspace_root"
            )
            capability_payload = None
            if self._agent_capabilities_provider is not None:
                capability_payload = await _maybe_await(
                    self._agent_capabilities_provider(agent_id, workspace_root)
                )
            await self.send_json(
                "agent.capabilities",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "agent_id": agent_id,
                    "workspace_root": workspace_root,
                    "capabilities": dict(capability_payload)
                    if isinstance(capability_payload, Mapping)
                    else {},
                },
            )
            return
        if message_type == "agent.prompt.preview.request":
            # feat-379-M2 R5: IM asked Gateway to assemble a prompt preview.
            # Gateway calls agent HTTP /v1/prompt-preview and returns the result.
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            agent_id = _require_text(body.get("agent_id"), field_name="agent_id")
            workspace_root = _require_text(
                body.get("workspace_root"), field_name="workspace_root"
            )
            features = body.get("features") or {}
            if not isinstance(features, dict):
                features = {}
            custom_prompt_raw = body.get("custom_prompt")
            custom_prompt = (
                custom_prompt_raw if isinstance(custom_prompt_raw, str) else None
            )
            tool_ids_raw = body.get("tool_ids") or []
            tool_ids = (
                [t for t in tool_ids_raw if isinstance(t, str)]
                if isinstance(tool_ids_raw, list)
                else []
            )
            skill_ids_raw = body.get("skill_ids") or []
            skill_ids = (
                [s for s in skill_ids_raw if isinstance(s, str)]
                if isinstance(skill_ids_raw, list)
                else []
            )
            scenario_raw = body.get("scenario")
            scenario = scenario_raw if isinstance(scenario_raw, str) else "direct"
            # feat-394-M9: heartbeat/cron gates moved to ctx.flags (FEATURE_REGISTRY).
            # heartbeat_enabled/cron_enabled extraction and forwarding retired;
            # callers pass {"heartbeat": true} in the features dict instead.
            preview_result: dict[str, object] = {}
            if self._prompt_preview_provider is not None:
                result = await _maybe_await(
                    self._prompt_preview_provider(
                        agent_id,
                        workspace_root,
                        features,
                        custom_prompt,
                        tool_ids,
                        scenario,
                        skill_ids,
                    )
                )
                if isinstance(result, Mapping):
                    preview_result = dict(result)
            await self.send_json(
                "agent.prompt.preview",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "preview": preview_result,
                },
            )
            return
        if message_type == "node.prompt.preview.request":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            node_workspace_root_raw = body.get("workspace_root")
            node_workspace_root = (
                node_workspace_root_raw
                if isinstance(node_workspace_root_raw, str)
                else ""
            )
            workspace_mode_raw = body.get("workspace_mode")
            if (
                isinstance(workspace_mode_raw, str)
                and self._node_prompt_workspace_resolver is not None
            ):
                agent_id_hint_raw = body.get("agent_id_hint")
                agent_id_hint = (
                    agent_id_hint_raw if isinstance(agent_id_hint_raw, str) else None
                )
                custom_root = (
                    node_workspace_root_raw
                    if isinstance(node_workspace_root_raw, str)
                    else None
                )
                try:
                    node_workspace_root = self._node_prompt_workspace_resolver(
                        workspace_mode_raw, agent_id_hint, custom_root
                    )
                except ValueError as exc:
                    await self.send_json(
                        "node.prompt.preview",
                        {
                            "request_id": request_id,
                            "node_id": self._reporter.node_id,
                            "preview": {
                                "error": {
                                    "code": "workspace_parent_unusable",
                                    "detail": str(exc),
                                }
                            },
                        },
                    )
                    return
            features = body.get("features") or {}
            if not isinstance(features, dict):
                features = {}
            custom_prompt_raw = body.get("custom_prompt")
            custom_prompt = (
                custom_prompt_raw if isinstance(custom_prompt_raw, str) else None
            )
            tool_ids_raw = body.get("tool_ids") or []
            tool_ids = (
                [t for t in tool_ids_raw if isinstance(t, str)]
                if isinstance(tool_ids_raw, list)
                else []
            )
            skill_ids_raw = body.get("skill_ids") or []
            skill_ids = (
                [s for s in skill_ids_raw if isinstance(s, str)]
                if isinstance(skill_ids_raw, list)
                else []
            )
            scenario_raw = body.get("scenario")
            scenario = scenario_raw if isinstance(scenario_raw, str) else "direct"
            node_preview_result: dict[str, object] = {}
            if self._prompt_preview_provider is not None:
                result = await _maybe_await(
                    self._prompt_preview_provider(
                        "",
                        node_workspace_root,
                        features,
                        custom_prompt,
                        tool_ids,
                        scenario,
                        skill_ids,
                    )
                )
                if isinstance(result, Mapping):
                    node_preview_result = dict(result)
            await self.send_json(
                "node.prompt.preview",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "preview": node_preview_result,
                },
            )
            return
        if message_type == "node.heartbeat.md.request":
            # feat-394-M13 (决策 G): IM asked gateway to read HEARTBEAT.md from the
            # agent's workspace.  IM never directly reads gateway-side workspace files
            # because IM and gateway may run on different hosts.
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            workspace_root_raw = body.get("workspace_root")
            workspace_root = (
                workspace_root_raw if isinstance(workspace_root_raw, str) else ""
            )
            content = ""
            if workspace_root:
                from pathlib import Path as _Path  # noqa: PLC0415 — avoid top-level import

                hb_path = _Path(workspace_root) / _PA_WORKSPACE_CFG_DIR / "HEARTBEAT.md"
                if hb_path.exists():
                    try:
                        content = hb_path.read_text(encoding="utf-8")
                    except OSError:
                        content = ""
            await self.send_json(
                "node.heartbeat.md",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "content": content,
                },
            )
            return
        if message_type == "node.cron.jobs.request":
            # feat-394-M13 (决策 G): IM asked gateway to read cron/jobs.json from the
            # agent's workspace.  Gateway reads its own file and returns the list.
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            workspace_root_raw = body.get("workspace_root")
            workspace_root = (
                workspace_root_raw if isinstance(workspace_root_raw, str) else ""
            )
            jobs: list = []
            if workspace_root:
                import json as _json  # noqa: PLC0415
                from pathlib import Path as _Path  # noqa: PLC0415

                jobs_path = (
                    _Path(workspace_root) / _PA_WORKSPACE_CFG_DIR / "cron" / "jobs.json"
                )
                if jobs_path.exists():
                    try:
                        data = _json.loads(jobs_path.read_text(encoding="utf-8"))
                        if isinstance(data, list):
                            jobs = data
                    except (OSError, _json.JSONDecodeError):
                        jobs = []
            await self.send_json(
                "node.cron.jobs",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "jobs": jobs,
                },
            )
            return
        if message_type == "node.skills.usage.request":
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            agent_id = _require_text(body.get("agent_id"), field_name="agent_id")
            workspace_root_raw = body.get("workspace_root")
            workspace_root = (
                workspace_root_raw if isinstance(workspace_root_raw, str) else ""
            )
            usage = _build_skills_usage_payload(
                agent_id=agent_id,
                node_id=self._reporter.node_id,
                workspace_root=workspace_root,
            )
            await self.send_json(
                "node.skills.usage",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "usage": usage,
                },
            )
            return
        if message_type == "node.cron.delete.request":
            # feat-394-M13 (決策 G): IM asked gateway to remove a specific job from
            # cron/jobs.json.  Gateway performs the file mutation and reports whether
            # the job was found and removed.
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            job_id_raw = body.get("job_id")
            job_id = job_id_raw if isinstance(job_id_raw, str) else ""
            workspace_root_raw = body.get("workspace_root")
            workspace_root = (
                workspace_root_raw if isinstance(workspace_root_raw, str) else ""
            )
            deleted = False
            if workspace_root and job_id:
                import json as _json  # noqa: PLC0415
                from pathlib import Path as _Path  # noqa: PLC0415

                jobs_path = (
                    _Path(workspace_root) / _PA_WORKSPACE_CFG_DIR / "cron" / "jobs.json"
                )
                if jobs_path.exists():
                    try:
                        data = _json.loads(jobs_path.read_text(encoding="utf-8"))
                        if isinstance(data, list):
                            filtered = [
                                item
                                for item in data
                                if isinstance(item, dict)
                                and str(item.get("id", "")) != job_id
                            ]
                            if len(filtered) < len(data):
                                jobs_path.write_text(
                                    _json.dumps(filtered, indent=2, ensure_ascii=False),
                                    encoding="utf-8",
                                )
                                deleted = True
                    except (OSError, _json.JSONDecodeError):
                        deleted = False
            await self.send_json(
                "node.cron.delete",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "deleted": deleted,
                },
            )
            return
        if message_type == "node.streaming_delta":
            # IM → PA direction: currently only permission_response kind is routed here.
            # Other kinds (turn_start, message_delta, …) are PA→IM only and would be
            # unexpected inbound; they are safely ignored.
            kind = body.get("kind")
            if (
                kind == "permission_response"
                and self._permission_response_handler is not None
            ):
                self._permission_response_handler(body)
            return
        if message_type == "error":
            # IM sends `type=error` when it rejects a PA-sent frame (e.g. malformed node.report
            # with missing node_id, or a payload whose FK reference does not exist). It is the
            # negative ack for the serialized matching frame: finish that frame's waiter, then
            # keep the connection alive and flush later valid frames. An uncorrelated error is
            # still recorded without guessing which independent request it belongs to.
            error_code = body.get("code")
            error_message = body.get("message")
            rejected_type = self._reject_pending_frame(body)
            self._events.append(
                {
                    "event": "error_ack",
                    "type": "error",
                    "code": error_code,
                    "message": error_message,
                    "rejected_type": rejected_type,
                    "message_type": rejected_type,
                }
            )
            if rejected_type in {"node.register", "node.heartbeat"}:
                await self._disconnect_current_websocket(
                    RuntimeError(
                        f"{error_code or 'protocol_error'}: "
                        f"{error_message or 'control frame rejected'} "
                        f"({rejected_type})"
                    )
                )
            elif rejected_type is not None:
                await self._flush_pending_frames()
            return
        raise ValueError(f"unsupported downstream message type: {message_type}")

    async def _flush_pending_frames(
        self,
        *,
        raise_on_disconnect: bool = False,
        disconnect_on_cancel: bool = True,
    ) -> None:
        async with self._flush_lock:
            if self._wire_frame_owner is not None or not self._connected:
                return
            lane: Literal["control", "business"]
            if self._pending_control_frames:
                pending_frame = self._pending_control_frames.popleft()
                lane = "control"
            elif self._registered and self._pending_frames:
                pending_frame = self._pending_frames.popleft()
                lane = "business"
            else:
                return
            owner = WireFrameOwner(
                frame=pending_frame,
                lane=lane,
                phase="sending",
            )
            self._wire_frame_owner = owner
            try:
                business_timeout = (
                    self._config.normalized_business_ack_timeout_seconds()
                    if lane == "business"
                    else None
                )
                if business_timeout is None:
                    await self._send_frame(
                        pending_frame.message_type, pending_frame.payload
                    )
                else:
                    async with asyncio.timeout(business_timeout):
                        await self._send_frame(
                            pending_frame.message_type, pending_frame.payload
                        )
            except asyncio.CancelledError:
                if disconnect_on_cancel:
                    await self._disconnect_current_websocket(
                        RuntimeError(f"{pending_frame.message_type} send was cancelled")
                    )
                raise
            except Exception as exc:  # noqa: BLE001
                await self._disconnect_current_websocket(exc)
                if raise_on_disconnect:
                    raise
                return
            if pending_frame.send_completed is not None:
                pending_frame.send_completed.set()
            if self._wire_frame_owner is owner:
                owner.phase = "awaiting_result"
                if lane == "business" and business_timeout is not None:
                    self._start_business_ack_timeout(owner, business_timeout)
            elif self._wire_frame_owner is not None:
                raise RuntimeError("frame wire ownership changed during send")

    async def _send_frame(
        self, message_type: str, payload: Mapping[str, object]
    ) -> None:
        websocket = self._require_websocket()
        wire_payload = dict(payload)
        # Every Gateway business frame is node-scoped at the IM dispatcher.  The
        # registered local reporter is the authority; individual producers must not
        # be able to omit or select a different node identity.
        wire_payload["node_id"] = self._reporter.node_id
        frame = json.dumps(
            {"type": message_type, "payload": wire_payload}, ensure_ascii=False
        )
        await websocket.send(frame)
        self._events.append({"event": "sent", "type": message_type})

    async def _disconnect_current_websocket(self, exc: Exception | None = None) -> None:
        websocket = self._websocket
        heartbeat_task = self._heartbeat_task
        self._mark_disconnected(exc)
        if websocket is not None:
            try:
                await websocket.close()
            except Exception as close_exc:  # noqa: BLE001
                _log.warning(
                    "failed to close IM websocket during disconnect: %s", close_exc
                )
        if heartbeat_task is not None and heartbeat_task is not asyncio.current_task():
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

    def _ack_pending_frame(self, payload: Mapping[str, object]) -> PendingFrame | None:
        owner = self._wire_frame_owner
        if owner is None:
            return None
        awaiting = owner.frame.message_type
        ack_type = payload.get("message_type")
        if not isinstance(ack_type, str) or ack_type.strip() != awaiting:
            return None
        pending_frame = owner.frame
        self._stop_business_ack_timeout()
        self._wire_frame_owner = None
        if pending_frame.ack_future is not None and not pending_frame.ack_future.done():
            pending_frame.ack_future.set_result(dict(payload))
        self._events.append({"event": "acked", "type": awaiting})
        self._finish_external_shadow_run(pending_frame)
        self._mark_outbound_drained_if_idle()
        return pending_frame

    def _resolve_correlated_channel_result(
        self, *, message_type: str, payload: Mapping[str, object]
    ) -> bool:
        source_type = {
            "channel.status.result": "channel.status",
            "channel.runtime_metadata.result": "channel.runtime_metadata",
            "channels.reconcile.result.ack": "channel.reconcile.result",
            "channels.bootstrap.result": "channels.bootstrap",
        }[message_type]
        owner = self._wire_frame_owner
        if (
            owner is None
            or owner.lane != "business"
            or owner.frame.message_type != source_type
        ):
            return False
        pending = owner.frame
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or request_id != pending.payload.get(
            "request_id"
        ):
            return False
        self._stop_business_ack_timeout()
        self._wire_frame_owner = None
        if pending.ack_future is not None and not pending.ack_future.done():
            pending.ack_future.set_result(dict(payload))
        self._events.append(
            {
                "event": "channel_result",
                "type": source_type,
                "outcome": payload.get("outcome") or payload.get("head_outcome"),
            }
        )
        self._mark_outbound_drained_if_idle()
        return True

    def _reject_pending_frame(self, payload: Mapping[str, object]) -> str | None:
        """Terminally reject the single in-flight frame selected by wire FIFO.

        IM serializes one response per upstream frame, while this client sends only
        one unacknowledged queued frame at a time.  A generic protocol error therefore
        belongs to the current head even when an older server omits request metadata.
        Releasing it here preserves the connection and lets unrelated work continue.
        """
        owner = self._wire_frame_owner
        if owner is None:
            return None
        pending = owner.frame
        awaiting = pending.message_type
        self._stop_business_ack_timeout()
        self._wire_frame_owner = None
        code = str(payload.get("code") or "protocol_error")
        message = str(payload.get("message") or "upstream frame rejected")
        if pending.ack_future is not None and not pending.ack_future.done():
            pending.ack_future.set_exception(
                IMFrameRejectedError(
                    f"IM rejected {awaiting} frame ({code}): {message}", code=code
                )
            )
        self._finish_external_shadow_run(pending)
        self._events.append(
            {
                "event": "rejected",
                "type": awaiting,
                "code": code,
                "message": message,
            }
        )
        self._mark_outbound_drained_if_idle()
        return awaiting

    def _start_heartbeat_loop(self) -> None:
        interval = self._config.normalized_heartbeat_interval_seconds()
        if interval is None:
            return
        existing = self._heartbeat_task
        if existing is not None and not existing.done():
            return
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(interval), name="personal-assistant-im-heartbeat"
        )

    async def _notify_registered(self) -> None:
        """Run post-register convergence only after IM confirms the node identity."""
        if self._on_connected is None:
            return
        try:
            await self._on_connected(self)
        except Exception as exc:  # noqa: BLE001
            self._events.append({"event": "on_connected_error", "error": str(exc)})

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
                    await self._send_heartbeat_and_wait_ack()
                except Exception as exc:  # noqa: BLE001
                    await self._disconnect_current_websocket(exc)
                    return
        except asyncio.CancelledError:
            raise

    async def _send_heartbeat_and_wait_ack(self) -> None:
        loop = asyncio.get_running_loop()
        ack_future: asyncio.Future[dict[str, object]] = loop.create_future()
        self._heartbeat_ack_future = ack_future
        timeout = self._config.normalized_heartbeat_ack_timeout_seconds()
        heartbeat = PendingFrame(
            message_type="node.heartbeat",
            payload=dict(self._reporter.send_heartbeat(status="online")),
            ack_future=ack_future,
        )
        self._outbound_drained_event().clear()
        self._pending_control_frames.append(heartbeat)
        try:
            if timeout is None:
                await self._flush_pending_frames()
                await asyncio.shield(ack_future)
                return
            try:
                async with asyncio.timeout(timeout):
                    # The timeout owner must report a precise send-vs-ack liveness
                    # failure.  Let it disconnect after converting cancellation to
                    # TimeoutError instead of logging a generic send cancellation here.
                    await self._flush_pending_frames(disconnect_on_cancel=False)
                    await asyncio.shield(ack_future)
            except TimeoutError as exc:
                owner = self._wire_frame_owner
                phase = (
                    "ack"
                    if owner is not None
                    and owner.frame is heartbeat
                    and owner.phase == "awaiting_result"
                    else "send"
                )
                raise TimeoutError(
                    f"IM heartbeat {phase} timed out after {timeout:.2f}s"
                ) from exc
        finally:
            if self._heartbeat_ack_future is ack_future:
                self._heartbeat_ack_future = None
            if not ack_future.done():
                ack_future.cancel()
            else:
                with contextlib.suppress(asyncio.CancelledError):
                    ack_future.exception()
            self._pending_control_frames = deque(
                frame
                for frame in self._pending_control_frames
                if frame is not heartbeat
            )

    def _mark_disconnected(self, exc: Exception | None = None) -> None:
        had_connection = self._connected or self._websocket is not None
        owner = self._wire_frame_owner
        business_frame = (
            owner.frame if owner is not None and owner.lane == "business" else None
        )
        control_frames = list(self._pending_control_frames)
        if owner is not None and owner.lane == "control":
            control_frames.append(owner.frame)
        heartbeat_ack_future = self._heartbeat_ack_future
        retained_business_frames: deque[PendingFrame] = deque()
        dropped_business_frames: list[PendingFrame] = []
        for pending in self._pending_frames:
            if pending.requeue_on_disconnect:
                retained_business_frames.append(pending)
            else:
                dropped_business_frames.append(pending)
        self._pending_frames = retained_business_frames
        self._connected = False
        self._websocket = None
        self._registered = False
        self._connection_epoch += 1
        self._registration_deadline = None
        self._wire_frame_owner = None
        self._pending_control_frames.clear()
        self._heartbeat_ack_future = None
        self._stop_business_ack_timeout()
        self._stop_heartbeat_loop()
        for control_frame in control_frames:
            future = control_frame.ack_future
            if future is not None and not future.done():
                with contextlib.suppress(asyncio.InvalidStateError):
                    future.set_exception(
                        RuntimeError(
                            f"IM websocket disconnected before {control_frame.message_type} ack"
                        )
                    )
        if heartbeat_ack_future is not None and not heartbeat_ack_future.done():
            with contextlib.suppress(asyncio.InvalidStateError):
                heartbeat_ack_future.set_exception(
                    RuntimeError("IM websocket disconnected before heartbeat ack")
                )
        if business_frame is not None:
            self._fail_pending_frame(
                business_frame,
                exc
                if isinstance(exc, TimeoutError)
                else RuntimeError("IM websocket disconnected before ack"),
            )
        for dropped in dropped_business_frames:
            self._fail_pending_frame(
                dropped,
                RuntimeError(
                    "external shadow live frame dropped before IM acknowledgement"
                ),
            )
        if business_frame is not None:
            if not business_frame.requeue_on_disconnect:
                self._events.append(
                    {
                        "event": "dropped",
                        "type": business_frame.message_type,
                        "reason": "external_shadow_recovery",
                    }
                )
            elif self._is_status_superseded_by_pending(business_frame):
                self._events.append(
                    {
                        "event": "superseded",
                        "type": business_frame.message_type,
                        "request_id": business_frame.payload.get("request_id"),
                    }
                )
            else:
                self._pending_frames.appendleft(business_frame)
        if had_connection:
            event: dict[str, object] = {"event": "disconnected"}
            if exc is not None:
                event["error"] = str(exc)
            self._events.append(event)

    def _classify_external_shadow_frame(self, pending: PendingFrame) -> None:
        """Keep durable external live projections out of reconnect replay."""

        if pending.message_type != "node.streaming_delta":
            return
        run_id = pending.payload.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            return
        if pending.payload.get("kind") == "turn_start" and pending.payload.get(
            "shadow_message_id"
        ):
            self._external_shadow_run_ids.add(run_id)
        if run_id in self._external_shadow_run_ids:
            pending.requeue_on_disconnect = False

    def _finish_external_shadow_run(self, pending: PendingFrame) -> None:
        if pending.message_type != "node.streaming_delta":
            return
        if pending.payload.get("kind") not in {
            "message_completed",
            "message_discarded",
        }:
            return
        run_id = pending.payload.get("run_id")
        if isinstance(run_id, str):
            self._external_shadow_run_ids.discard(run_id)

    def finish_external_shadow_run(self, run_id: str) -> None:
        """Release reconnect classification when the observer reaches run terminal."""

        self._external_shadow_run_ids.discard(run_id)

    def _start_business_ack_timeout(
        self, owner: WireFrameOwner, timeout_seconds: float
    ) -> None:
        self._stop_business_ack_timeout()

        async def _watch() -> None:
            try:
                await asyncio.sleep(timeout_seconds)
                if self._wire_frame_owner is owner and owner.phase == "awaiting_result":
                    await self._disconnect_current_websocket(
                        TimeoutError(
                            "IM business frame "
                            f"{owner.frame.message_type} ack timed out after "
                            f"{timeout_seconds:.2f}s"
                        )
                    )
            except asyncio.CancelledError:
                raise
            finally:
                if self._business_ack_timeout_task is asyncio.current_task():
                    self._business_ack_timeout_task = None

        self._business_ack_timeout_task = asyncio.create_task(
            _watch(), name="personal-assistant-im-business-ack-timeout"
        )

    def _stop_business_ack_timeout(self) -> None:
        task = self._business_ack_timeout_task
        self._business_ack_timeout_task = None
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    @staticmethod
    def _fail_pending_frame(pending: PendingFrame, exc: Exception) -> None:
        if pending.send_completed is not None:
            pending.send_completed.set()
        future = pending.ack_future
        if future is not None and not future.done():
            # The event loop serializes ownership, but suppressing InvalidStateError keeps
            # disconnect cleanup safe if a test double resolves between the two calls.
            with contextlib.suppress(asyncio.InvalidStateError):
                future.set_exception(exc)

    def _require_websocket(self) -> ClientWebSocket:
        websocket = self._websocket
        if websocket is None:
            raise RuntimeError("IM websocket is not connected")
        return websocket


def _build_skills_usage_payload(
    *, agent_id: str, node_id: str, workspace_root: str
) -> dict[str, object]:
    """Read agent-local and shared .usage.json files for dashboard-ready stats."""
    empty = _empty_skills_usage_payload(agent_id=agent_id, node_id=node_id)
    if not workspace_root:
        return empty
    workspace_path = Path(workspace_root).expanduser()
    workspace_session_ids = _workspace_session_ids(workspace_path)
    records: list[tuple[str, Mapping[str, object]]] = []
    for usage_path, shared in _iter_usage_paths(workspace_path):
        if not usage_path.exists():
            continue
        try:
            raw = json.loads(usage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for skill_id, item in _iter_skill_usage_records(raw):
            filtered = (
                _filter_shared_usage_for_workspace(
                    item,
                    workspace_session_ids=workspace_session_ids,
                )
                if shared
                else item
            )
            if filtered is None:
                continue
            records.append((skill_id, filtered))
    if not records:
        return empty
    today = datetime.now(timezone.utc).date()
    skills: list[dict[str, object]] = []
    heatmap_data = [0] * 30
    health = {
        "created_auto_total": 0,
        "active_auto_total": 0,
        "used_auto_total": 0,
    }
    for skill_id, item in records:
        source = _string_or_default(item.get("source"), "unknown")
        state = _string_or_default(item.get("state"), "active")
        use_count = _int_or_zero(item.get("use_count"))
        session_refs = _normalize_session_refs(item.get("session_refs"))
        trend_buckets = _trend_buckets(session_refs=session_refs, today=today)
        for index, value in enumerate(trend_buckets):
            heatmap_data[index] += value
        if source in {"F3", "F4"}:
            health["created_auto_total"] += 1
            if state != "archived":
                health["active_auto_total"] += 1
            if use_count > 0:
                health["used_auto_total"] += 1
        recent_call_keys = [
            key
            for key in (_session_ref_key(ref) for ref in session_refs)
            if key is not None
        ][:10]
        name = _string_or_default(item.get("name"), skill_id)
        skills.append(
            {
                "skill_id": skill_id,
                "name": name,
                "source": source,
                "state": state,
                "use_count": use_count,
                "last_used_at": _optional_string(item.get("last_used_at")),
                "created_at": _optional_string(item.get("created_at")),
                "archived_at": _optional_string(item.get("archived_at")),
                "archive_error": _optional_string(item.get("archive_error")),
                "session_refs": session_refs,
                "recent_call_keys": recent_call_keys,
                "trend_buckets": trend_buckets,
            }
        )
    skills.sort(
        key=lambda skill: (
            _parse_iso_datetime(skill.get("last_used_at"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    return {
        "agent_id": agent_id,
        "node_id": node_id,
        "skills": skills,
        "heatmap_data": heatmap_data,
        "health": health,
    }


def _iter_usage_paths(workspace_root: Path) -> list[tuple[Path, bool]]:
    paths: list[tuple[Path, bool]] = []
    seen: set[Path] = set()
    local = workspace_root / _PA_WORKSPACE_CFG_DIR / "skills" / ".usage.json"
    paths.append((local, False))
    seen.add(local.expanduser().resolve())
    for root in _PA_SHARED_SKILL_ROOTS:
        shared = root.expanduser() / ".usage.json"
        try:
            key = shared.resolve()
        except OSError:
            key = shared
        if key in seen:
            continue
        seen.add(key)
        paths.append((shared, True))
    return paths


def _workspace_session_ids(workspace_root: Path) -> frozenset[str]:
    sessions_dir = workspace_root / _PA_WORKSPACE_CFG_DIR / "sessions"
    if not sessions_dir.is_dir():
        return frozenset()
    return frozenset(path.stem for path in sessions_dir.rglob("*.jsonl"))


def _filter_shared_usage_for_workspace(
    item: Mapping[str, object], *, workspace_session_ids: frozenset[str]
) -> Mapping[str, object] | None:
    if not workspace_session_ids:
        return None
    session_refs = [
        ref
        for ref in _normalize_session_refs(item.get("session_refs"))
        if ref.get("session_id") in workspace_session_ids
    ]
    if not session_refs:
        return None
    filtered = dict(item)
    filtered["session_refs"] = session_refs
    filtered["use_count"] = len(session_refs)
    timestamps = [
        ref["timestamp"]
        for ref in session_refs
        if isinstance(ref.get("timestamp"), str) and ref.get("timestamp")
    ]
    if timestamps:
        filtered["last_used_at"] = max(timestamps)
    return filtered


def _empty_skills_usage_payload(*, agent_id: str, node_id: str) -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "node_id": node_id,
        "skills": [],
        "heatmap_data": [0] * 30,
        "health": {
            "created_auto_total": 0,
            "active_auto_total": 0,
            "used_auto_total": 0,
        },
    }


def _iter_skill_usage_records(raw: object) -> list[tuple[str, Mapping[str, object]]]:
    if isinstance(raw, Mapping):
        records: list[tuple[str, Mapping[str, object]]] = []
        for skill_id, item in raw.items():
            if isinstance(item, Mapping):
                records.append((str(skill_id), item))
        return records
    if isinstance(raw, list):
        records = []
        for index, item in enumerate(raw):
            if not isinstance(item, Mapping):
                continue
            skill_id = _string_or_default(item.get("skill_id"), f"skill-{index + 1}")
            records.append((skill_id, item))
        return records
    return []


def _normalize_session_refs(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    refs: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        ref: dict[str, str] = {}
        for key in ("session_id", "tool_call_id", "timestamp"):
            item_value = item.get(key)
            if isinstance(item_value, str) and item_value:
                ref[key] = item_value
        if ref:
            refs.append(ref)
    return refs


def _trend_buckets(*, session_refs: list[dict[str, str]], today: date) -> list[int]:
    buckets = [0] * 30
    first_day = today - timedelta(days=29)
    for ref in session_refs:
        timestamp = _parse_iso_datetime(ref.get("timestamp"))
        if timestamp is None:
            continue
        event_day = timestamp.date()
        if event_day < first_day or event_day > today:
            continue
        buckets[(event_day - first_day).days] += 1
    return buckets


def _session_ref_key(ref: Mapping[str, str]) -> str | None:
    session_id = ref.get("session_id")
    tool_call_id = ref.get("tool_call_id")
    if session_id and tool_call_id:
        return f"{session_id}:{tool_call_id}"
    return session_id or tool_call_id


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _string_or_default(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_or_zero(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(value))
        except ValueError:
            return 0
    return 0


async def _maybe_await(
    value: Awaitable[Mapping[str, object] | None] | Mapping[str, object] | None,
) -> Mapping[str, object] | None:
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


def _require_mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value
