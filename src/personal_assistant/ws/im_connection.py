"""Gateway-side IM websocket client with reconnect/backoff and downstream dispatch."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

from personal_assistant._utils import _require_text
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.defaults import (
    WORKSPACE_CONFIG_DIRNAME as _PA_WORKSPACE_CFG_DIR,
)
from personal_assistant.reporter.upstream_reporter import UpstreamReporter

_log = logging.getLogger("personal_assistant.ws.im_connection")


@dataclass(slots=True)
class PendingFrame:
    """Track one queued upstream frame plus its optional ack waiter."""

    message_type: str
    payload: dict[str, object]
    ack_future: asyncio.Future[dict[str, object]] | None = field(
        default=None, repr=False
    )


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
PermissionResponseHandler = Callable[[Mapping[str, object]], None]
# feat-445-M1: IM delegates session fork over WS. Given the fork request payload
# (source_conversation_id / new_conversation_id / agent_id / fork_point.message_id),
# the gateway-side handler locates the source kernel session, forks it at the point,
# binds the new conversation, and returns {ok, new_session_id?, error?}.
SessionForkHandler = Callable[
    [Mapping[str, object]],
    Awaitable[Mapping[str, object]] | Mapping[str, object],
]


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
        agent_capabilities_provider: AgentCapabilitiesProvider | None = None,
        node_capabilities_provider: NodeCapabilitiesProvider | None = None,
        prompt_preview_provider: PromptPreviewProvider | None = None,
        session_fork_handler: SessionForkHandler | None = None,
        token_getter: TokenGetter | None = None,
        permission_response_handler: PermissionResponseHandler | None = None,
        on_connected: Callable[[], Awaitable[None]] | None = None,
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
        self._node_capabilities_provider = node_capabilities_provider
        # feat-379-M2 R5: provider for prompt preview; calls agent HTTP /v1/prompt-preview.
        self._prompt_preview_provider = prompt_preview_provider
        # feat-445-M1: handler for IM-delegated session fork (decision 2).
        self._session_fork_handler = session_fork_handler
        # Called when IM pushes a permission_response so PA can POST it to the agent.
        self._permission_response_handler = permission_response_handler
        # token_getter is called on each connect attempt to supply a fresh access token.
        # When absent the static config.token is used (backwards-compatible behaviour).
        self._token_getter = token_getter
        # feat-394-M12 决策 F: async callback invoked after each successful WS bind
        # (node.register ack received). Used to trigger reconcile_all_agents so gateway
        # config converges to IM truth on connect and every reconnect.
        self._on_connected = on_connected
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
        # bugfix-446-M1 (decision 3 guard): set after the first connect attempt resolves
        # (success OR failure). Heartbeat startup waits on this so the first tick never
        # fires before the initial handshake has had a chance to complete — without it,
        # removing the eager connect_once would regress feat-393 (the delivery observer
        # silently drops while not connected).  Lazily created so it binds to the loop
        # that actually runs run_forever.
        self._first_connect_resolved: asyncio.Event | None = None

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
        # feat-394-M12 决策 F: fire on_connected after WS bind succeeds so reconcile
        # runs on every connect and reconnect. Errors in the callback are logged and
        # suppressed — a reconcile failure must not tear down the WS connection.
        if self._on_connected is not None:
            try:
                await self._on_connected()
            except Exception as exc:  # noqa: BLE001
                self._events.append({"event": "on_connected_error", "error": str(exc)})

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

        self._pending_frames.append(
            PendingFrame(message_type=message_type, payload=dict(payload))
        )
        await self._flush_pending_frames()

    async def send_json_await_ack(
        self, message_type: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        """Queue one frame and wait until the matching ack payload arrives."""

        loop = asyncio.get_running_loop()
        ack_future: asyncio.Future[dict[str, object]] = loop.create_future()
        self._pending_frames.append(
            PendingFrame(
                message_type=message_type, payload=dict(payload), ack_future=ack_future
            )
        )
        await self._flush_pending_frames()
        return await ack_future

    async def send_agent_message(self, payload: Mapping[str, object]) -> IMDispatchAck:
        """Send one agent.message frame and return the parsed IM dispatch ack."""

        ack_payload = await self.send_json_await_ack("agent.message", payload)
        return IMDispatchAck.from_payload(ack_payload)

    def _first_attempt_event(self) -> asyncio.Event:
        # Lazily created so it binds to whichever loop runs run_forever / the waiter.
        if self._first_connect_resolved is None:
            self._first_connect_resolved = asyncio.Event()
        return self._first_connect_resolved

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
                await self._listen_once()
            except asyncio.CancelledError:
                self._mark_disconnected()
                raise
            except Exception as exc:  # noqa: BLE001
                self._mark_disconnected(exc)
                if self._stop_requested:
                    break
                await self._sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._config.reconnect_max_seconds
                )
            finally:
                first_attempt.set()

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
                created_payload = await _maybe_await(
                    self._agent_create_handler(agent_payload)
                )
            await self.send_json(
                "agent.created",
                {
                    "request_id": request_id,
                    "node_id": self._reporter.node_id,
                    "agent": dict(created_payload)
                    if isinstance(created_payload, Mapping)
                    else {},
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
            # feat-379-M9 (決策 11): node-level preview — no agent_id needed.
            # feat-383-M1: workspace_root and skill_ids now carried in the frame (IM derives workspace_root).
            request_id = _require_text(body.get("request_id"), field_name="request_id")
            # workspace_root may be empty string when agent_id_hint was absent in the IM request.
            node_workspace_root_raw = body.get("workspace_root")
            node_workspace_root = (
                node_workspace_root_raw
                if isinstance(node_workspace_root_raw, str)
                else ""
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

                hb_path = _Path(workspace_root) / "HEARTBEAT.md"
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
            # with missing node_id, or a payload whose FK reference doesn't exist in the DB).
            # Raising here would propagate into run_forever's `except Exception` → _mark_disconnected
            # → reconnect loop, severing the connection on every bad frame. The right behaviour is to
            # log the error and keep the connection alive so subsequent valid frames can still be
            # delivered. The upstream frame that triggered the error was already sent; nothing to ack.
            error_code = body.get("code")
            error_message = body.get("message")
            self._events.append(
                {
                    "event": "error_ack",
                    "type": "error",
                    "code": error_code,
                    "message": error_message,
                }
            )
            return
        raise ValueError(f"unsupported downstream message type: {message_type}")

    async def _flush_pending_frames(self, *, raise_on_disconnect: bool = False) -> None:
        async with self._flush_lock:
            if self._awaiting_ack_type is not None or not self._pending_frames:
                return
            pending_frame = self._pending_frames[0]
            try:
                await self._send_frame(
                    pending_frame.message_type, pending_frame.payload
                )
            except Exception as exc:  # noqa: BLE001
                await self._disconnect_current_websocket(exc)
                if raise_on_disconnect:
                    raise
                return
            self._awaiting_ack_type = pending_frame.message_type

    async def _send_frame(
        self, message_type: str, payload: Mapping[str, object]
    ) -> None:
        websocket = self._require_websocket()
        frame = json.dumps(
            {"type": message_type, "payload": dict(payload)}, ensure_ascii=False
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
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(interval), name="personal-assistant-im-heartbeat"
        )

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
                    await self._send_frame(
                        "node.heartbeat", self._reporter.send_heartbeat(status="online")
                    )
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
        if (
            pending_frame is not None
            and pending_frame.ack_future is not None
            and not pending_frame.ack_future.done()
        ):
            # bugfix-446-M1 decision 6 (pure defense): guard the TOCTOU where the future
            # is resolved between the done() check and set_exception. The single event
            # loop makes this practically unreachable, but the suppress is zero-cost.
            with contextlib.suppress(asyncio.InvalidStateError):
                pending_frame.ack_future.set_exception(
                    RuntimeError("IM websocket disconnected before ack")
                )
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
