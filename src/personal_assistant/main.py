"""Process entry for the personal assistant Node Gateway runtime."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import logging
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
import tempfile
import webbrowser
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

_log = logging.getLogger("personal_assistant.main")
_PA_GLOBAL_SKILL_ROOT = Path("~/.nanoassistant/skills")

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.channels.web_relay_adapter import (
    RelayDeduplicationStore,
    WebRelayAdapter,
)
from personal_assistant.channels.feishu import FeishuAdapter

from personal_assistant.config.local_store import (
    ChannelConfig,
    HeartbeatConfig,
    IMServiceConfig,
    LocalConfig,
    WORKSPACE_CONFIG_DIRNAME as _WCD,
    default_local_config_path,
    ensure_feishu_doc_skill_for_feishu_agents,
    load_local_config,
    resolve_run_model,
    save_local_config,
)
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog, LiveAgentSnapshot
from personal_assistant.gateway.agent_config_sync import (
    IMAgentConfigSync,
    _im_http_base_url,
    _im_http_headers,
    _make_workspace_root_factory,
    _parse_heartbeat_from_im_payload,  # noqa: F401 - compatibility re-export
)
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
)
from personal_assistant.gateway.image_attachments import ImageAttachmentResolver
from personal_assistant.gateway.inbound_dispatcher import InboundDispatcher
from personal_assistant.gateway.inbound_pipeline import (
    InboundPipeline,
    InboundRouteConfig,
)
from personal_assistant.gateway.runtime_delivery.context import (
    RunDeliveryContextStore,
)
from personal_assistant.gateway.runtime_delivery.background import (
    build_bg_reply_sender as _build_bg_reply_sender,
    build_session_event_callback as _build_session_event_callback,
)
from personal_assistant.gateway.runtime_delivery.lifecycle import (
    build_relay_lifecycle_callback as _build_relay_lifecycle_callback,
)
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer as _build_kernel_event_observer,
    extract_ack_message_id as _extract_ack_message_id,  # noqa: F401
    roll_bubble as _roll_bubble,  # noqa: F401
)
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)
from personal_assistant.gateway.runtime_delivery.stream import (
    stream_run_to_completion as _stream_run_to_completion,
)
from personal_assistant.gateway.internal_dispatch import (
    InternalDispatchEndpoint,
    InternalDispatchHandler,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.session_keys import (
    PersistentSessionBindingStore,
    build_conversation_session_key,
    build_external_session_key,
)
from personal_assistant.gateway.session_binder import (
    ConversationBindingRequest,
    GatewaySessionBinder,
)
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator
from personal_assistant.gateway.shadow_sync import IMShadowConversationSync
from personal_assistant.reporter.upstream_reporter import (
    UpstreamReporter,
    build_agent_capabilities_payload,
    build_node_capabilities_payload,
    build_runtime_capabilities,
)
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)
from personal_assistant.scheduler.cron_scheduler import (
    CronJobStore,
    CronScheduler,
    CronSchedulerStateStore,
)
from personal_assistant.scheduler.cron_execution_service import (
    CronExecutionService,
    CronRunStreamDelivery,
)
from personal_assistant.scheduler.cron_runner import CronRunner
from personal_assistant.scheduler.cron_service_registry import CronServiceRegistry
from personal_assistant.auth.im_auth_client import IMAuthClient, IMAuthError
from personal_assistant.ws.im_connection import (
    AgentCreateHandler,
    IMConnectionConfig,
    IMConnectionManager,
    PromptPreviewProvider,
    SessionForkHandler,
)


ProcessLike = subprocess.Popen[Any]
BackgroundProcessFactory = Callable[[list[str], Path], ProcessLike]
StartWaiter = Callable[[ProcessLike, LocalConfig, float], None]
Monotonic = Callable[[], float]
Sleep = Callable[[float], None]
AsyncConnect = Callable[[str, Mapping[str, str]], Awaitable[ClientConnection]]
SignalHandlerInstaller = Callable[[], Callable[[], None]]
BootstrapClientFactory = Callable[[str], httpx.Client]
FeedbackSink = Callable[[str, str, str | None], None]


class GatewayStartupError(RuntimeError):
    """Represent one actionable startup failure shown to gateway operators.

    Args:
        summary: Human-readable failure summary.
        next_step: Optional concrete remediation step shown alongside the error.
    """

    def __init__(self, *, summary: str, next_step: str | None = None) -> None:
        cleaned_summary = summary.strip()
        cleaned_next_step = (
            next_step.strip()
            if isinstance(next_step, str) and next_step.strip()
            else None
        )
        super().__init__(cleaned_summary)
        self.summary = cleaned_summary
        self.next_step = cleaned_next_step


def _read_log_last_error(
    log_path: Path, *, offset: int = 0, lines: int = 20
) -> str | None:
    """Return the last non-empty line written after *offset* bytes, or None if unreadable."""
    try:
        with log_path.open("rb") as f:
            f.seek(offset)
            chunk = f.read().decode("utf-8", errors="replace")
        tail = [l for l in chunk.splitlines()[-lines:] if l.strip()]
        return tail[-1] if tail else None
    except Exception:  # noqa: BLE001
        return None


def _check_im_reachable(url: str) -> bool:
    """Return True if the IM service HTTP endpoint responds within 1 second."""
    try:
        httpx.get(url, timeout=1.0, trust_env=False)
        return True
    except Exception:  # noqa: BLE001
        return False


def _print_gateway_started(result: "BackgroundLaunchResult") -> None:
    print(f"Gateway started (pid={result.pid})")
    if result.im_service_url is not None:
        reachable = _check_im_reachable(result.im_service_url)
        status = (
            "connected" if reachable else "unavailable (running offline, will retry)"
        )
        print(f"IM service:      {result.im_service_url}  [{status}]")
    print(f"Log:             {result.log_path}")


def _emit_gateway_feedback(
    level: str, summary: str, next_step: str | None = None
) -> None:
    """Print one operator-facing gateway feedback line to stderr."""

    if level == "ERROR":
        print("Gateway failed to start\n", file=sys.stderr)
        for line in summary.splitlines():
            print(f"  {line}", file=sys.stderr)
        if next_step is not None:
            print(f"\n  → {next_step}", file=sys.stderr)
    else:
        print(f"{level} {summary}", file=sys.stderr)
        if next_step is not None:
            print(f"  → {next_step}", file=sys.stderr)


class GatewayRuntimeLike(Protocol):
    """Describe the minimal lifecycle contract used by `run_gateway`."""

    def run_forever(self) -> int:
        """Run the gateway until shutdown and return the process exit code."""


class HeartbeatRunner(Protocol):
    """Describe the async lifecycle expected from the heartbeat runner wrapper."""

    async def start(self) -> None:
        """Start background scheduler ticking."""

    def request_stop(self) -> None:
        """Synchronously reject future scheduler passes."""

    async def close(self, deadline: float) -> None:
        """Wait for the current pass by the shared shutdown deadline."""


class IMConnectionManagerLike(Protocol):
    """Describe the async lifecycle required from the optional IM connector."""

    async def connect_once(self) -> None:
        """Establish the initial websocket connection and register the node."""

    async def run_forever(self) -> None:
        """Keep the websocket alive until close is requested."""

    async def wait_first_connect_attempt(self, *, timeout: float = ...) -> None:
        """Block until the first connect attempt resolves (success or failure).

        Bounded by ``timeout``; heartbeat startup gates on this (bugfix-446-M1
        decision 3 guard).
        """

    async def close(self) -> None:
        """Close the websocket and stop reconnect attempts."""

    async def drain(self, deadline: float) -> None:
        """Wait for all accepted outbound frames to be acknowledged."""


class BrowserOpener(Protocol):
    """Describe the minimal browser-launch interface needed by bind bootstrap."""

    def __call__(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
        """Open one browser URL and report whether a handler accepted the request."""


@dataclass(frozen=True, slots=True)
class RuntimeFactories:
    """Collect replaceable construction hooks used by the gateway entry.

    Args:
        load_config: Function used to load YAML config into `LocalConfig`.
        build_runtime: Factory that creates the runtime orchestrator from config.
        install_signal_handlers: Optional hook that installs OS signal handlers before run.
    """

    load_config: Callable[[str | Path], LocalConfig] = load_local_config
    build_runtime: Callable[[LocalConfig], GatewayRuntimeLike] | None = None
    install_signal_handlers: SignalHandlerInstaller | None = None


@dataclass(frozen=True, slots=True)
class BackgroundLaunchResult:
    """Describe the operator-facing result of a successful background launch.

    Args:
        pid: Process id of the detached foreground child now hosting the gateway runtime.
        log_path: File receiving the detached child stdout/stderr stream.
        im_service_url: Optional IM service URL configured for this gateway.
    """

    pid: int
    log_path: Path
    im_service_url: str | None = None


@dataclass(frozen=True, slots=True)
class GatewayRuntimeState:
    """Persist the operator-facing metadata needed to locate one background gateway.

    Args:
        pid: Background gateway process id launched for this config.
        config_path: Absolute config path used for that process.
        log_path: Log file receiving the detached process output.
        process_start: OS process birth identity. ``None`` identifies legacy state.
    """

    pid: int
    config_path: str
    log_path: str
    process_start: str | None = None


class _IMBootstrapClient:
    """Query IM ownership state and launch browser binding when a node is unbound.

    Args:
        base_url: HTTP base URL used for IM account and node APIs.
        token: Optional bearer token forwarded to IM HTTP APIs.
        client: Optional preconfigured HTTP client used by tests.
        browser_opener: Function used to open the operator browser on pending bind URLs.
        timeout_seconds: HTTP timeout used for node/bind bootstrap calls.
        monotonic: Monotonic clock source used for short startup polling windows.
        sleep: Sleep function used between node-visibility retries.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None,
        client: httpx.Client | None = None,
        client_factory: BootstrapClientFactory | None = None,
        browser_opener: BrowserOpener = webbrowser.open,
        feedback_sink: FeedbackSink = _emit_gateway_feedback,
        timeout_seconds: float = 5.0,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleep = time.sleep,
        token_getter: Callable[[], Awaitable[str | None]] | None = None,
    ) -> None:
        self._base_urls = _im_bootstrap_base_urls(base_url)
        self._base_headers = _im_http_headers(token)
        self._timeout_seconds = timeout_seconds
        self._client_factory = client_factory
        self._clients: dict[str, httpx.Client] = {}
        self._base_url = self._base_urls[0]
        if client is not None:
            self._clients[self._base_url] = client
        self._browser_opener = browser_opener
        self._feedback_sink = feedback_sink
        self._monotonic = monotonic
        self._sleep = sleep
        self._token_getter = token_getter

    def _refresh_token(self) -> None:
        # bootstrap 跑在 asyncio.to_thread 工作线程里(main.py:894-896),无运行中 event
        # loop,因此可以直接 asyncio.run 同步等异步 token_getter。fix bugfix-346 漏接
        # bootstrap 路径导致 username/password 配置首次启动 401 的问题。
        if self._token_getter is None:
            return
        token = asyncio.run(self._token_getter())
        if token:
            self._base_headers = _im_http_headers(token)
            for client in self._clients.values():
                client.headers.update(self._base_headers)

    def ensure_node_binding(self, *, node_id: str) -> str | None:
        """Open the bind URL when the upstream node still has no owner.

        Args:
            node_id: Gateway node id that was just registered over IM websocket.

        Returns:
            The opened bind URL for unbound nodes, or `None` when the node is already owned.

        Raises:
            GatewayStartupError: When IM bootstrap APIs do not expose the registered
                node or binding cannot be started/confirmed.
        """

        self._refresh_token()
        owner_id, resolved_base_url = self._wait_for_owner(node_id=node_id)
        if owner_id:
            return None
        client = self._get_client(resolved_base_url)
        try:
            response = client.post(
                "/im/v1/bind", json={"action": "start", "node_id": node_id}
            )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise GatewayStartupError(
                summary=f"node {node_id} could not start IM binding",
                next_step=f"Verify {resolved_base_url}/im/v1/bind is reachable, then rerun gateway.",
            ) from exc
        payload = response.json()
        bind_url = _require_text(payload.get("bind_url"), field_name="bind_url")

        # refactor-381: when NANO_MULTIAGENT_AUTO_BIND=1 (or --auto-bind via CLI),
        # confirm the binding programmatically instead of asking the operator to
        # click a URL. Removes the worktree-e2e blocker where automation cannot
        # complete the interactive bind step.
        if os.environ.get("NANO_MULTIAGENT_AUTO_BIND") == "1":
            bind_token = _extract_bind_token(bind_url)
            if not bind_token:
                raise GatewayStartupError(
                    summary=f"node {node_id} auto-bind failed: bind_url missing token",
                    next_step=f"Inspect {bind_url} or unset NANO_MULTIAGENT_AUTO_BIND.",
                )
            try:
                confirm_resp = client.post(
                    "/im/v1/bind",
                    json={"action": "confirm", "bind_token": bind_token},
                )
                confirm_resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                raise GatewayStartupError(
                    summary=f"node {node_id} auto-bind confirm failed",
                    next_step=(
                        f"POST {resolved_base_url}/im/v1/bind with action=confirm + bind_token failed. "
                        "Verify the IM Bearer token has confirm permission, then rerun."
                    ),
                ) from exc
            self._feedback_sink(
                "INFO",
                f"node {node_id} auto-bound to IM",
                f"NANO_MULTIAGENT_AUTO_BIND=1 confirmed bind for {resolved_base_url}.",
            )
            return None

        self._browser_opener(bind_url, new=2, autoraise=True)
        self._feedback_sink(
            "ACTION",
            f"node {node_id} is waiting for IM binding",
            f"Open {bind_url} to finish binding this node.",
        )
        return bind_url

    def close(self) -> None:
        """Release the owned HTTP client."""

        seen_ids: set[int] = set()
        for client in self._clients.values():
            client_id = id(client)
            if client_id in seen_ids:
                continue
            seen_ids.add(client_id)
            client.close()

    def _wait_for_owner(self, *, node_id: str) -> tuple[str, str]:
        deadline = self._monotonic() + 5.0
        last_error: Exception | None = None
        while self._monotonic() <= deadline:
            for base_url in self._base_urls:
                try:
                    return self._get_owner_id(
                        node_id=node_id, base_url=base_url
                    ), base_url
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self._sleep(0.1)
        checked_urls = ", ".join(
            f"{base_url}/im/v1/nodes" for base_url in self._base_urls
        )
        message = f"node {node_id} did not appear in IM bootstrap"
        next_step = (
            f"Verify the IM node API is reachable at {checked_urls} and rerun gateway."
        )
        if last_error is not None:
            raise GatewayStartupError(
                summary=message, next_step=next_step
            ) from last_error
        raise GatewayStartupError(summary=message, next_step=next_step)

    def _get_owner_id(self, *, node_id: str, base_url: str) -> str:
        response = self._get_client(base_url).get("/im/v1/nodes")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("nodes response must be a list")
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            if _require_text(item.get("node_id"), field_name="node_id") != node_id:
                continue
            owner_id = item.get("owner_id")
            return owner_id.strip() if isinstance(owner_id, str) else ""
        raise RuntimeError(f"node {node_id} not found")

    def _get_client(self, base_url: str) -> httpx.Client:
        client = self._clients.get(base_url)
        if client is not None:
            return client
        if self._client_factory is not None:
            client = self._client_factory(base_url)
        else:
            client = httpx.Client(
                base_url=base_url,
                headers=self._base_headers,
                timeout=self._timeout_seconds,
                trust_env=False,
            )
        self._clients[base_url] = client
        return client


class PollingHeartbeatRunner:
    """Run the existing heartbeat scheduler as a background tick loop.

    Args:
        scheduler: Existing scheduler implementation that evaluates `HEARTBEAT.md`.
        config: Local heartbeat runtime settings.
        sleep: Async sleep function used between tick passes.
        kernel: In-process kernel used to stream heartbeat run events (feat-393).
            When provided alongside run_context_store and owner_user_id, the runner
            seeds run_context_store and awaits each run to terminal state, driving the
            kernel_event_observer to create the heartbeat IM message if there is content.
        run_context_store: Shared delivery context store seeded with heartbeat run
            metadata (feat-393). Observer reads the same store to route streaming
            events to IM.
        owner_user_id: IM user_id of the gateway node owner; used as to_user_id in
            turn_start so the heartbeat message lands in the owner's direct conversation
            with the agent (feat-393).

    Notes:
        The runner keeps scheduler semantics local and configuration-driven. It does not
        introduce hot reload or remote orchestration; it only provides the missing long-
        running process wrapper required to keep the gateway alive.
    """

    def __init__(
        self,
        *,
        scheduler: HeartbeatScheduler,
        config: HeartbeatConfig,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        kernel: Any | None = None,
        run_context_store: "dict[str, dict[str, str]] | RunDeliveryContextStore | None" = None,
        owner_user_id: str = "",
        kernel_event_observer: Any | None = None,
        cron_tick_fn: Callable[[str], Awaitable[None]] | None = None,
        agent_catalog: LiveAgentCatalog | None = None,
        session_binder: GatewaySessionBinder | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._config = config
        self._sleep = sleep
        self._stop_requested = False
        self._wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        # feat-393: kernel + run_context_store enable streaming delivery of heartbeat results.
        self._kernel = kernel
        self._run_context_store = run_context_store
        self._owner_user_id = owner_user_id
        self._kernel_event_observer = kernel_event_observer
        # feat-394-M3 CRITICAL-1 fix: wire cron into the unified polling tick.
        # cron_tick_fn(agent_id) is called once per tick for each cron_enabled agent.
        # When None, cron is skipped (backward compat, no cron subsystem configured).
        self._cron_tick_fn = cron_tick_fn
        self._agent_catalog = agent_catalog
        self._session_binder = session_binder

    async def start(self) -> None:
        """Start background scheduler ticking exactly once."""

        if self._task is not None:
            return
        self._stop_requested = False
        self._wake_event.clear()
        self._task = asyncio.create_task(
            self._run_loop(), name="personal-assistant-heartbeat"
        )
        # bugfix-446-M1 decision 4: observe a truly unexpected loop crash instead of
        # letting it die silently (issue path 4). Mirrors the inbound dispatcher pattern.
        self._task.add_done_callback(_consume_task_exception)

    def request_stop(self) -> None:
        """Synchronously stop admission without joining the current tick."""

        self._stop_requested = True
        self._wake_event.set()

    async def close(self, deadline: float | None = None) -> None:
        """Drain or cancel the current tick by an absolute loop deadline.

        Args:
            deadline: Shared Gateway ``loop.time()`` deadline. ``None`` preserves
                the standalone caller behavior of waiting without a timeout.

        Raises:
            TimeoutError: When the current tick requires deadline cancellation.
        """

        task = self._task
        if task is None:
            return
        self.request_stop()
        try:
            if deadline is None:
                await task
                return
            remaining = max(0.0, deadline - asyncio.get_running_loop().time())
            _, pending = await asyncio.wait((task,), timeout=remaining)
            if not pending:
                await task
                return
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise TimeoutError("heartbeat tick exceeded Gateway shutdown deadline")
        finally:
            self._task = None

    def request_tick(self) -> None:
        """Wake the loop so a manual IM-triggered tick can run promptly."""

        self._wake_event.set()

    async def _run_loop(self) -> None:
        while not self._stop_requested:
            # bugfix-446-M1 decision 4: a failing scheduler tick must not kill the loop —
            # log and fall through to the interval wait so the next tick can recover (the
            # cron tick below already follows this pattern; issue path 4 was the bare await).
            try:
                summary = await self._scheduler.tick()
            except Exception:  # noqa: BLE001
                _log.exception(
                    "heartbeat scheduler tick failed; retrying next interval"
                )
                summary = None
            # feat-393: consume each triggered heartbeat run through the shared observer so
            # results are delivered to the owner's canonical IM direct conversation.
            if (
                summary is not None
                and self._kernel is not None
                and self._run_context_store is not None
                and self._owner_user_id
            ):
                for record in summary.triggered_runs:
                    if self._stop_requested:
                        break
                    await self._consume_heartbeat_run(record)
            # feat-394-M3 CRITICAL-1 fix: unified polling tick also drives cron scheduling.
            # Design §架构总览: "统一 Polling 调度 tick（扩展现 PollingHeartbeatRunner）".
            # For each agent with cron_enabled=True, invoke the cron tick function.
            if self._cron_tick_fn is not None and not self._stop_requested:
                active_agents = (
                    (
                        (snapshot.agent_id, snapshot.config)
                        for snapshot in self._agent_catalog.values_snapshot()
                    )
                    if self._agent_catalog is not None
                    else ()
                )
                for agent_id, agent in active_agents:
                    if self._stop_requested:
                        break
                    cron_enabled = getattr(agent, "cron_enabled", False)
                    if cron_enabled:
                        try:
                            await self._cron_tick_fn(agent_id)
                        except Exception:  # noqa: BLE001
                            import logging as _logging  # noqa: PLC0415

                            _logging.getLogger(__name__).exception(
                                "cron tick failed: agent=%s", agent_id
                            )
            if self._stop_requested:
                break
            try:
                await asyncio.wait_for(
                    self._wake_event.wait(), timeout=self._config.tick_interval_seconds
                )
            except TimeoutError:
                continue
            finally:
                self._wake_event.clear()

    @staticmethod
    async def trim_silent_tick(
        *,
        session_file: "Path",
        pre_submit_line_count: int,
    ) -> None:
        """Truncate a JSONL session file to remove heartbeat turns added by a silent tick.

        feat-394 decision 3 (transcript trim): after a silent heartbeat run (HEARTBEAT_OK
        or empty response), the triggering prompt and ack turns are removed from the
        canonical direct-chat session so they do not pollute the next LLM context window.
        "Silent" is detected by the caller when run_context_store[run_id]["conversation_id"]
        remains empty after the run completes (no turn_start was ever sent — zero IM trace).

        The trim reads all lines, keeps only the first ``pre_submit_line_count`` non-empty
        lines, and rewrites the file atomically (rename after write).  Lines beyond that
        count are the heartbeat trigger prompt + HEARTBEAT_OK (or empty) assistant turn.

        This approach is safe because:
        - JSONL append is the only mutation normally done; we own the file.
        - The rewrite is atomic (tmp file → rename) so a crash mid-write does not
          corrupt existing history.
        - heartbeat-only turns do not refresh session idle time (design §B requirement).

        Args:
            session_file: Absolute path to the session ``.jsonl`` file.
            pre_submit_line_count: Number of non-empty lines present before the heartbeat
                run was submitted.  Lines beyond this index are removed.
        """

        import os  # noqa: PLC0415

        if not session_file.exists():
            return  # nothing to trim
        raw_text = session_file.read_text(encoding="utf-8")
        all_lines = raw_text.splitlines(keepends=True)
        # Count only non-empty lines to match the pre-submit count.
        non_empty_indices: list[int] = []
        for idx, line in enumerate(all_lines):
            if line.strip():
                non_empty_indices.append(idx)
        if len(non_empty_indices) <= pre_submit_line_count:
            return  # nothing to trim (no heartbeat lines were appended)
        # Keep lines up to and including the last pre-submit non-empty line.
        last_kept_line_idx = (
            non_empty_indices[pre_submit_line_count - 1]
            if pre_submit_line_count > 0
            else -1
        )
        kept_lines = all_lines[: last_kept_line_idx + 1]
        tmp_path = session_file.with_suffix(".jsonl.trim_tmp")
        try:
            tmp_path.write_text("".join(kept_lines), encoding="utf-8")
            os.replace(tmp_path, session_file)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    async def _consume_heartbeat_run(self, record: "HeartbeatRunRecord") -> None:
        """Stream one heartbeat run to completion, driving the kernel_event_observer for IM delivery.

        Delegates streaming to the module-level _stream_run_to_completion helper, then applies
        heartbeat-specific post-processing: silent-tick transcript trim (feat-394 decision 3-B).
        The observer handles lazy turn_start creation and NO_REPLY/empty suppression.

        Args:
            record: HeartbeatRunRecord returned by the scheduler tick.

        Notes:
            Failures are logged and swallowed; the next tick will re-evaluate and re-report
            if the condition persists.  This matches design decision 6: heartbeat delivery
            inherits normal-chat failure behavior (no persistent retry).
        """
        _hb_logger = _log  # module-level logger; no per-call import needed

        run_id = record.run_id
        kernel_session_id = record.session_id
        agent_id = record.agent_id

        assert self._run_context_store is not None  # guard (checked in _run_loop)

        # feat-394 decision 3 transcript trim (B): snapshot session file line count before run.
        # After a silent tick (HEARTBEAT_OK / empty), the triggered prompt + ack turns are
        # removed so they don't pollute the canonical session's next LLM context window.
        # We also don't refresh session idle time for heartbeat-only ticks.
        _session_file_for_trim: "Path | None" = None
        _pre_submit_line_count = 0
        try:
            _get_session_fn = getattr(self._kernel, "get_session", None)
            if _get_session_fn is not None:
                _sess_info = _get_session_fn(kernel_session_id)
                _ws_root = (
                    _sess_info.get("workspace_root")
                    if isinstance(_sess_info, dict)
                    else None
                )
                if _ws_root:
                    _sess_path = (
                        Path(_ws_root)
                        / _WCD
                        / "sessions"
                        / f"{kernel_session_id}.jsonl"
                    )
                    if _sess_path.exists():
                        _session_file_for_trim = _sess_path
                        _content = _sess_path.read_text(encoding="utf-8")
                        _pre_submit_line_count = sum(
                            1 for ln in _content.splitlines() if ln.strip()
                        )
        except Exception:  # noqa: BLE001
            pass  # trim snapshot failure is non-fatal; trim skipped for this tick

        try:
            # feat-393 fix-r2 Fix B: stream from the pre-submit anchor to skip replaying
            # history from prior ticks.  Falls back to 0 when anchor is absent (test path).
            outcome = await _stream_run_to_completion(
                run_id=run_id,
                kernel_session_id=kernel_session_id,
                agent_id=agent_id,
                owner_user_id=self._owner_user_id,
                kernel=self._kernel,
                run_context_store=self._run_context_store,
                observer=self._kernel_event_observer,
                stream_anchor=record.stream_anchor,
            )
            ctx = outcome.context
        except Exception:  # noqa: BLE001  — delivery failure does not disrupt gateway loop
            _hb_logger.exception(
                "heartbeat run delivery failed: agent=%s run_id=%s", agent_id, run_id
            )
            return

        # feat-394 B: silent-tick transcript trim.
        # If conversation_id was never filled (no turn_start sent → zero IM trace → silent tick),
        # truncate the session JSONL back to the pre-submit state.
        _was_silent = ctx is not None and not ctx.get("conversation_id")
        if (
            _was_silent
            and _session_file_for_trim is not None
            and _pre_submit_line_count > 0
        ):
            try:
                await self.trim_silent_tick(
                    session_file=_session_file_for_trim,
                    pre_submit_line_count=_pre_submit_line_count,
                )
            except Exception:  # noqa: BLE001
                _hb_logger.debug(
                    "heartbeat transcript trim failed (non-fatal): agent=%s run_id=%s",
                    agent_id,
                    run_id,
                )


async def _run_kernel_background_analysis(
    kernel: Any,
    *,
    workspace_root: Path,
    prompt: str,
    tool_allowlist: tuple[str, ...],
    metadata: dict[str, Any],
) -> Any:
    session = await kernel.create_session(
        workspace_root=workspace_root,
        enabled_tools=list(tool_allowlist),
        metadata=metadata,
    )
    run = kernel.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": prompt}],
        workspace_root=workspace_root,
    )
    run_id = getattr(run, "run_id", "")
    for _ in range(300):
        current = kernel.get_run(run_id)
        status = getattr(current, "status", "")
        if status == "completed":
            return current
        if status in {"failed", "cancelled"}:
            raise RuntimeError(f"skill batch review background run {status}")
        await asyncio.sleep(0.1)
    raise TimeoutError("skill batch review background run timed out")


def _session_ids_from_skill_batch_trigger(trigger: Any) -> tuple[str, ...]:
    refs = getattr(trigger, "session_refs", ())
    if not isinstance(refs, (tuple, list)):
        return ()
    session_ids: list[str] = []
    for ref in refs:
        if not isinstance(ref, Mapping):
            continue
        session_id = ref.get("session_id")
        if isinstance(session_id, str) and session_id:
            session_ids.append(session_id)
    return tuple(session_ids)


class GatewayRuntime:
    """Run the assembled Node Gateway process until shutdown is requested.

    Args:
        config: Parsed immutable local gateway config.
        channel_registry: Registry containing configured channel adapters.
        heartbeat_runner: Background heartbeat loop wrapper.
        im_connection_manager: Optional IM websocket connector.
        on_inbound: Shared synchronous inbound callback given to channel adapters.
        im_watchdog_initial_seconds: Initial backoff before the watchdog rebuilds the IM
            maintenance loop after an abnormal exit (mirrors the IM reconnect policy).
        im_watchdog_max_seconds: Cap for the watchdog rebuild backoff.
        resource_closers: Additional cleanup callables invoked after runtime shutdown.
    """

    def __init__(
        self,
        config: LocalConfig,
        *,
        channel_registry: ChannelRegistry | None = None,
        heartbeat_runner: HeartbeatRunner | None = None,
        im_connection_manager: IMConnectionManagerLike | None = None,
        on_inbound: Callable[[InboundMessage], None] | None = None,
        im_watchdog_initial_seconds: float = 1.0,
        im_watchdog_max_seconds: float = 60.0,
        resource_closers: tuple[Callable[[], None], ...] = (),
        feedback_sink: FeedbackSink = _emit_gateway_feedback,
        internal_dispatch_handler: InternalDispatchHandler | None = None,
        internal_dispatch_endpoint: InternalDispatchEndpoint | None = None,
        gateway_internal_port: int = 8089,
        kernel: object | None = None,
        cron_dispatcher: CronServiceRegistry | None = None,
        run_coordinator: SessionRunCoordinator | None = None,
        runtime_delivery_tasks: RuntimeDeliveryTaskTracker | None = None,
    ) -> None:
        self._config = config
        self._channel_registry = channel_registry or ChannelRegistry()
        self._heartbeat_runner = heartbeat_runner
        self._im_connection_manager = im_connection_manager
        self._on_inbound = on_inbound or (lambda _message: None)
        self._im_watchdog_initial_seconds = im_watchdog_initial_seconds
        self._im_watchdog_max_seconds = im_watchdog_max_seconds
        self._resource_closers = resource_closers
        self._feedback_sink = feedback_sink
        self._internal_dispatch_handler = internal_dispatch_handler
        self._internal_dispatch_endpoint = internal_dispatch_endpoint
        self._gateway_internal_port = gateway_internal_port
        # bugfix-402-M3 R3: explicit kernel reference for ordered async shutdown
        # (Decision 7). Kernel is closed via aclose() between producers and consumers,
        # not via the untyped resource_closers list.
        self._kernel = kernel
        # bugfix-402-M4: inject gateway loop into cron services so enqueue() from
        # worker threads (asyncio.to_thread) can schedule execute_fn correctly.
        self._cron_dispatcher = cron_dispatcher
        self._inbound_dispatcher = (
            on_inbound if isinstance(on_inbound, InboundDispatcher) else None
        )
        self._run_coordinator = run_coordinator
        self._runtime_delivery_tasks = runtime_delivery_tasks
        self._ready_event = threading.Event()
        self._shutdown_requested = threading.Event()
        self._shutdown_request_lock = threading.Lock()
        self._shutdown_started_at: float | None = None
        self._shutdown_async_event: asyncio.Event | None = None
        self._shutdown_loop: asyncio.AbstractEventLoop | None = None

    def wait_until_ready(self, timeout: float | None = None) -> bool:
        """Block until the runtime reaches ready state or timeout expires."""

        return self._ready_event.wait(timeout)

    def request_shutdown(self) -> None:
        """Request graceful shutdown from another thread or signal handler."""

        with self._shutdown_request_lock:
            if not self._shutdown_requested.is_set():
                self._shutdown_started_at = time.monotonic()
                self._shutdown_requested.set()
        loop = self._shutdown_loop
        event = self._shutdown_async_event
        if loop is not None and event is not None and loop.is_running():
            loop.call_soon_threadsafe(event.set)

    def run_forever(self) -> int:
        """Run the gateway until shutdown is requested.

        Returns:
            `0` after startup succeeds and graceful shutdown completes.
        """

        self._ready_event.clear()
        with self._shutdown_request_lock:
            self._shutdown_requested.clear()
            self._shutdown_started_at = None
        return asyncio.run(self._run_until_shutdown())

    async def _run_until_shutdown(self) -> int:
        loop = asyncio.get_running_loop()
        self._shutdown_loop = loop
        self._shutdown_async_event = asyncio.Event()
        if self._inbound_dispatcher is not None:
            self._inbound_dispatcher.bind_loop(loop)
        # bugfix-402-M4: wire gateway loop into cron dispatcher so enqueue()
        # called from asyncio.to_thread (tool.run) can schedule execute_fn on
        # this loop rather than silently dropping (no-running-loop path).
        if self._cron_dispatcher is not None:
            self._cron_dispatcher.set_gateway_loop(loop)

        channels_started = False
        heartbeat_started = False
        dispatch_runner: Any | None = None
        dispatch_site: Any | None = None
        im_task: asyncio.Task[None] | None = None
        try:
            build_dispatch_handler = getattr(
                self._internal_dispatch_handler, "build_aiohttp_handler", None
            )
            if callable(build_dispatch_handler):
                from aiohttp import web as _aiohttp_web

                _dispatch_app = _aiohttp_web.Application()
                _dispatch_app.router.add_post(
                    "/internal/dispatch",
                    build_dispatch_handler(),
                )
                dispatch_runner = _aiohttp_web.AppRunner(_dispatch_app)
                await dispatch_runner.setup()
                dispatch_site = _aiohttp_web.TCPSite(
                    dispatch_runner, "127.0.0.1", self._gateway_internal_port
                )
                await dispatch_site.start()
                dispatch_server = getattr(dispatch_site, "_server", None)
                dispatch_sockets = getattr(dispatch_server, "sockets", ())
                if not dispatch_sockets:
                    raise RuntimeError(
                        "internal dispatch listener started without a bound socket"
                    )
                actual_port = int(dispatch_sockets[0].getsockname()[1])
                if self._internal_dispatch_endpoint is not None:
                    self._internal_dispatch_endpoint.publish(
                        host="127.0.0.1", port=actual_port
                    )
            start_channels(self._channel_registry, self._on_inbound)
            channels_started = True
            await self._run_skill_maintenance()
            self._install_skill_batch_review_scheduler()
            self._ready_event.set()
            if self._im_connection_manager is not None:
                # bugfix-446-M1 (decision 1): own the IM connection through a
                # watchdog-supervised loop. The eager connect_once / post_im_connect that
                # used to run here were issue paths 1/2 — a transient startup fault killed
                # the gateway. Connection (first handshake + node binding via on_connected)
                # is now driven entirely by the supervised run_forever; a transient failure
                # just retries, and an abnormal loop exit is rebuilt by the watchdog.
                im_task = asyncio.create_task(
                    self._supervise_im_connection(self._im_connection_manager),
                    name="personal-assistant-im",
                )
            if self._heartbeat_runner is not None:
                # feat-393 guard (decision 3 companion): with the eager connect_once gone,
                # gate the first heartbeat tick on the first connect attempt resolving so
                # the delivery observer never drops a tick fired before the handshake. The
                # wait is bounded internally, so an unreachable/hung IM cannot block startup.
                if self._im_connection_manager is not None:
                    await self._im_connection_manager.wait_first_connect_attempt()
                await self._heartbeat_runner.start()
                heartbeat_started = True
            await self._wait_for_shutdown_request()
            return 0
        finally:
            shutdown_started_at = self._shutdown_started_at or loop.time()
            inner_deadline = shutdown_started_at + (
                0.8 * self._config.gateway.shutdown_grace_seconds
            )
            self._ready_event.clear()
            if self._internal_dispatch_endpoint is not None:
                self._internal_dispatch_endpoint.clear()

            # Admission seal is deliberately synchronous: active HTTP handlers,
            # heartbeat ticks and inbound roots remain consumers until after Kernel
            # terminal events have crossed their delivery boundaries.
            if self._inbound_dispatcher is not None:
                self._run_shutdown_action(
                    "inbound dispatcher seal", self._inbound_dispatcher.seal
                )
            if self._internal_dispatch_handler is not None:
                self._run_shutdown_action(
                    "internal dispatch seal", self._internal_dispatch_handler.seal
                )
            if heartbeat_started and self._heartbeat_runner is not None:
                self._run_shutdown_action(
                    "heartbeat request_stop", self._heartbeat_runner.request_stop
                )
            if self._cron_dispatcher is not None:
                self._run_shutdown_action(
                    "cron request_stop", self._cron_dispatcher.request_stop
                )
            if channels_started:
                self._run_shutdown_action(
                    "channel stop", lambda: stop_channels(self._channel_registry)
                )

            if self._inbound_dispatcher is not None:
                await self._run_shutdown_operation(
                    "inbound admission settle",
                    inner_deadline,
                    lambda: self._inbound_dispatcher.settle_admission(inner_deadline),
                    enforce_deadline=False,
                )

            # Kernel close precedes physical consumer drain so accepted runs can
            # publish their final lifecycle through still-live subscribers/delivery.
            if self._kernel is not None and hasattr(self._kernel, "aclose"):
                await self._run_shutdown_operation(
                    "kernel close",
                    inner_deadline,
                    self._kernel.aclose,
                )

            consumer_drains: list[
                tuple[str, Callable[[], Awaitable[object]], bool]
            ] = []
            if dispatch_runner is not None:
                consumer_drains.append(
                    ("internal dispatch", dispatch_runner.cleanup, True)
                )
            if heartbeat_started and self._heartbeat_runner is not None:
                consumer_drains.append(
                    (
                        "heartbeat",
                        lambda: self._heartbeat_runner.close(inner_deadline),
                        False,
                    )
                )
            if self._cron_dispatcher is not None:
                consumer_drains.append(
                    (
                        "cron",
                        lambda: self._cron_dispatcher.drain_all(inner_deadline),
                        False,
                    )
                )
            if self._inbound_dispatcher is not None:
                consumer_drains.append(
                    (
                        "inbound roots",
                        lambda: self._inbound_dispatcher.drain(inner_deadline),
                        False,
                    )
                )
            if self._run_coordinator is not None:
                consumer_drains.append(
                    (
                        "session run coordinator",
                        lambda: self._run_coordinator.drain(inner_deadline),
                        False,
                    )
                )
            if consumer_drains:
                await asyncio.gather(
                    *(
                        asyncio.create_task(
                            self._run_shutdown_operation(
                                name,
                                inner_deadline,
                                operation,
                                enforce_deadline=enforce_deadline,
                            ),
                            name=f"shutdown-drain:{name}",
                        )
                        for name, operation, enforce_deadline in consumer_drains
                    )
                )

            if self._runtime_delivery_tasks is not None:
                await self._run_shutdown_operation(
                    "runtime delivery",
                    inner_deadline,
                    lambda: self._runtime_delivery_tasks.close_and_drain(
                        inner_deadline
                    ),
                    enforce_deadline=False,
                )

            if self._im_connection_manager is not None:
                im_outbound_drain = getattr(
                    self._im_connection_manager, "drain", None
                )
                if callable(im_outbound_drain):
                    await self._run_shutdown_operation(
                        "IM outbound drain",
                        inner_deadline,
                        lambda: im_outbound_drain(inner_deadline),
                        enforce_deadline=False,
                    )
                await self._run_shutdown_operation(
                    "IM connection close",
                    inner_deadline,
                    self._im_connection_manager.close,
                )
            if im_task is not None:
                # issue path 3: cleanup must never be torn apart by a stored task
                # exception. It uses the same absolute deadline as transport close;
                # either timeout remains isolated so synchronous closers still run.
                await self._run_shutdown_operation(
                    "IM task await",
                    inner_deadline,
                    lambda: _await_background_task(im_task),
                )
            for closer in self._resource_closers:
                self._run_shutdown_action("resource closer", closer)
            self._shutdown_async_event = None
            self._shutdown_loop = None

    @staticmethod
    def _run_shutdown_action(name: str, action: Callable[[], None]) -> None:
        """Run one synchronous seal/close action without skipping later owners."""

        try:
            action()
        except BaseException as exc:  # noqa: BLE001
            _log.warning("%s raised during shutdown: %s", name, exc)

    @staticmethod
    async def _run_shutdown_operation(
        name: str,
        deadline: float,
        operation: Callable[[], Awaitable[object]],
        *,
        enforce_deadline: bool = True,
    ) -> None:
        """Run one async owner under the shared deadline with failure isolation."""

        try:
            if enforce_deadline:
                async with asyncio.timeout_at(deadline):
                    await operation()
            else:
                await operation()
        except BaseException as exc:  # noqa: BLE001
            _log.warning("%s raised during shutdown: %s", name, exc)

    def _shutdown_event_for_loop(self) -> asyncio.Event:
        loop = asyncio.get_running_loop()
        event = self._shutdown_async_event
        if event is None or self._shutdown_loop is not loop:
            event = asyncio.Event()
            self._shutdown_async_event = event
            self._shutdown_loop = loop
        if self._shutdown_requested.is_set():
            event.set()
        return event

    async def _run_skill_maintenance(self) -> None:
        """Run best-effort per-agent skill housekeeping at Gateway startup."""

        if self._kernel is None:
            return
        run_skill_maintenance = getattr(self._kernel, "run_skill_maintenance", None)
        drain = getattr(self._kernel, "run_queued_skill_batch_reviews", None)
        if not callable(run_skill_maintenance) and not callable(drain):
            return
        for agent in self._config.agents:
            workspace_root = getattr(agent, "workspace_root", None)
            if workspace_root is None:
                continue
            try:
                if callable(run_skill_maintenance):
                    run_skill_maintenance(workspace_root=workspace_root)
                if callable(drain):
                    skill_root = Path(workspace_root) / _WCD / "skills"
                    await drain(
                        run_background_analysis=self._build_skill_batch_analysis_runner(
                            workspace_root=workspace_root
                        ),
                        skill_root=skill_root,
                    )
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "skill maintenance failed for agent=%s workspace=%s: %s",
                    getattr(agent, "agent_id", ""),
                    workspace_root,
                    exc,
                )

    def _install_skill_batch_review_scheduler(self) -> None:
        if self._kernel is None:
            return
        setter = getattr(self._kernel, "set_skill_batch_review_drain_scheduler", None)
        if not callable(setter):
            return

        def _schedule(trigger: Any) -> None:
            workspace_root = self._workspace_root_for_skill_batch_trigger(trigger)
            if workspace_root is None:
                _log.warning(
                    "cannot drain skill batch review for skill=%s without a matching workspace",
                    getattr(trigger, "skill_name", ""),
                )
                return
            asyncio.create_task(
                self._drain_queued_skill_batch_reviews_for_workspace(
                    workspace_root=workspace_root
                ),
                name="personal-assistant-skill-batch-review",
            )

        setter(_schedule)

    def _workspace_root_for_skill_batch_trigger(self, trigger: Any) -> Path | None:
        session_ids = _session_ids_from_skill_batch_trigger(trigger)
        if session_ids:
            for agent in self._config.agents:
                workspace_root = getattr(agent, "workspace_root", None)
                if workspace_root is None:
                    continue
                session_dir = Path(workspace_root) / _WCD / "sessions"
                for session_id in session_ids:
                    if any(session_dir.rglob(f"{session_id}.jsonl")):
                        return Path(workspace_root)
        skill_root = getattr(trigger, "skill_root", None)
        if skill_root is not None:
            try:
                resolved_skill_root = Path(skill_root).expanduser().resolve()
            except TypeError:
                resolved_skill_root = None
            if resolved_skill_root is not None:
                for agent in self._config.agents:
                    workspace_root = getattr(agent, "workspace_root", None)
                    if workspace_root is None:
                        continue
                    local_skill_root = (
                        (Path(workspace_root) / _WCD / "skills").expanduser().resolve()
                    )
                    if resolved_skill_root == local_skill_root:
                        return Path(workspace_root)
        if len(self._config.agents) == 1:
            return Path(self._config.agents[0].workspace_root)
        return None

    async def _drain_queued_skill_batch_reviews_for_workspace(
        self, *, workspace_root: Path
    ) -> None:
        drain = getattr(self._kernel, "run_queued_skill_batch_reviews", None)
        if not callable(drain):
            return
        try:
            await drain(
                run_background_analysis=self._build_skill_batch_analysis_runner(
                    workspace_root=workspace_root
                ),
                skill_root=Path(workspace_root) / _WCD / "skills",
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "queued skill batch review drain failed for workspace=%s: %s",
                workspace_root,
                exc,
            )

    def _build_skill_batch_analysis_runner(
        self, *, workspace_root: Path
    ) -> Callable[..., Awaitable[Any]]:
        async def _run_background_analysis(
            prompt: str,
            *,
            tool_allowlist: tuple[str, ...],
            metadata: dict[str, Any],
        ) -> Any:
            return await _run_kernel_background_analysis(
                self._kernel,
                workspace_root=workspace_root,
                prompt=prompt,
                tool_allowlist=tool_allowlist,
                metadata=metadata,
            )

        return _run_background_analysis

    async def _wait_for_shutdown_request(self, *, timeout: float | None = None) -> bool:
        event = self._shutdown_event_for_loop()
        if self._shutdown_requested.is_set():
            event.set()
            return True
        if timeout is None:
            await event.wait()
            return True
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return self._shutdown_requested.is_set()
        return True

    async def _supervise_im_connection(self, manager: IMConnectionManagerLike) -> None:
        """Keep the IM maintenance loop alive (bugfix-446-M1 decision 1, watchdog).

        ``run_forever`` is expected to absorb transient faults internally and only return
        when ``close()`` is requested. If it instead returns or raises while shutdown has
        NOT been requested — the "silent death" of issue path 6 — rebuild it after an
        exponential backoff (mirroring the IM reconnect policy) so the node never gets
        stuck in a "neither reconnecting nor exiting" zombie state. ``CancelledError`` is
        propagated to honor task cancellation; process-control exceptions propagate too.
        """

        delay = self._im_watchdog_initial_seconds
        while not self._shutdown_requested.is_set():
            started_at = time.monotonic()
            try:
                await manager.run_forever()
            except asyncio.CancelledError:
                raise
            except (SystemExit, KeyboardInterrupt):
                raise
            except Exception:  # noqa: BLE001
                runtime = time.monotonic() - started_at
                if runtime >= self._im_watchdog_max_seconds:
                    delay = self._im_watchdog_initial_seconds
                _log.exception("IM maintenance loop crashed; watchdog will rebuild it")
            else:
                if self._shutdown_requested.is_set():
                    return
                if bool(getattr(manager, "_stop_requested", False)):
                    _log.info("IM maintenance loop stopped cleanly; watchdog exiting")
                    return
                runtime = time.monotonic() - started_at
                if runtime >= self._im_watchdog_max_seconds:
                    delay = self._im_watchdog_initial_seconds
                _log.warning("IM maintenance loop returned; watchdog will rebuild it")
            if self._shutdown_requested.is_set():
                return
            _log.warning(
                "IM maintenance loop rebuild scheduled in %.2fs",
                delay,
            )
            if await self._wait_for_shutdown_request(timeout=delay):
                return
            if self._shutdown_requested.is_set():
                return
            delay = min(delay * 2, self._im_watchdog_max_seconds)


def _load_runtime_config(
    config_path: str | Path,
    *,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    save_config: Callable[[LocalConfig, str | Path], None] = save_local_config,
    im_service_url_override: str | None = None,
) -> LocalConfig:
    config = load_config(config_path)
    config = _autofill_feishu_bot_open_id(
        config,
        save_config=save_config,
        bot_identity_fetcher=_infer_feishu_bot_open_id_from_app_credentials,
    )
    if (
        not isinstance(im_service_url_override, str)
        or not im_service_url_override.strip()
    ):
        return config
    override_url = im_service_url_override.strip()
    old_im = config.im_service
    if old_im is None:
        return replace(config, im_service=IMServiceConfig(url=override_url))
    return replace(
        config,
        im_service=IMServiceConfig(
            url=override_url,
            token=old_im.token,
            refresh_token=old_im.refresh_token,
            username=old_im.username,
            password=old_im.password,
        ),
    )


def _autofill_feishu_bot_open_id(
    config: LocalConfig,
    *,
    save_config: Callable[[LocalConfig, str | Path], None] = save_local_config,
    bot_identity_fetcher: Callable[[str, str, str], str | None] | None = None,
) -> LocalConfig:
    """Fill missing Feishu bot open IDs from app-credential runtime probes."""
    updated_channels: list[ChannelConfig] = []
    changed = False
    for channel in config.channels:
        if not channel.enabled or not channel.name.startswith("feishu:"):
            updated_channels.append(channel)
            continue
        settings = dict(channel.settings)
        bot_open_id = settings.get("botOpenId")
        needs_bot_open_id = not (isinstance(bot_open_id, str) and bot_open_id.strip())
        if not needs_bot_open_id:
            updated_channels.append(channel)
            continue
        app_id = settings.get("appId")
        if not isinstance(app_id, str) or not app_id.strip():
            updated_channels.append(channel)
            continue
        cleaned_app_id = app_id.strip()
        app_secret = settings.get("appSecret")
        domain = settings.get("domain")
        cleaned_domain = (
            domain.strip()
            if isinstance(domain, str) and domain.strip()
            else "https://open.feishu.cn"
        )
        if bot_identity_fetcher is None or not (
            isinstance(app_secret, str) and app_secret.strip()
        ):
            updated_channels.append(channel)
            continue
        inferred_bot_open_id = bot_identity_fetcher(
            cleaned_app_id, app_secret.strip(), cleaned_domain
        )
        if inferred_bot_open_id is None:
            updated_channels.append(channel)
            continue
        settings["botOpenId"] = inferred_bot_open_id
        updated_channels.append(replace(channel, settings=settings))
        changed = True
    if not changed:
        return config
    updated = replace(config, channels=tuple(updated_channels))
    source_path = getattr(updated, "source_path", None)
    if source_path is not None:
        save_config(updated, source_path)
    return updated


def _infer_feishu_bot_open_id_from_app_credentials(
    app_id: str, app_secret: str, domain: str
) -> str | None:
    """Return bot open_id by probing Feishu with app credentials."""
    try:
        from lark_oapi.channel.bot_identity import fetch_bot_identity
        from lark_oapi.core.model import Config
    except ImportError:
        _log.warning("lark-oapi bot identity helper unavailable; botOpenId not filled")
        return None

    sdk_config = Config()
    sdk_config.app_id = app_id
    sdk_config.app_secret = app_secret
    sdk_config.domain = domain
    sdk_config.timeout = 10
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            identity = asyncio.run(fetch_bot_identity(sdk_config))
        else:
            identity = _run_sync_in_thread(
                lambda: asyncio.run(fetch_bot_identity(sdk_config)),
                name="feishu-bot-id-probe",
            )
    except Exception:  # noqa: BLE001
        _log.warning("failed to probe Feishu bot identity", exc_info=True)
        return None

    open_id = getattr(identity, "open_id", None) if identity is not None else None
    if isinstance(open_id, str) and open_id.strip():
        return open_id.strip()
    _log.warning("Feishu bot identity probe returned no bot open_id")
    return None


def _run_sync_in_thread(func: Callable[[], Any], *, name: str) -> Any:
    result: list[Any] = []
    errors: list[BaseException] = []

    def _target() -> None:
        try:
            result.append(func())
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    thread = threading.Thread(target=_target, name=name, daemon=True)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    return result[0] if result else None


def run_gateway(
    *,
    config_path: str | Path,
    factories: RuntimeFactories | Mapping[str, Any] | None = None,
    im_service_url_override: str | None = None,
) -> int:
    """Load config, build runtime, and execute the gateway entry flow.

    Args:
        config_path: YAML config file passed by the operator.
        factories: Optional factory overrides used by tests.

    Returns:
        Process exit code. `0` means the managed startup/shutdown sequence succeeded.
    """

    resolved_factories = _coerce_factories(factories)
    config = _load_runtime_config(
        config_path,
        load_config=resolved_factories.load_config,
        im_service_url_override=im_service_url_override,
    )
    # refactor-406-M2: model registry init is build_kernel's responsibility (决策 5):
    # build_runtime → build_pa_kernel → build_kernel inits the registry from config.llm.
    builder = resolved_factories.build_runtime or build_runtime
    runtime = builder(config)
    restore_signal_handlers = (
        resolved_factories.install_signal_handlers
        or _install_default_signal_handlers(runtime)
    )
    restore = restore_signal_handlers()
    pid = os.getpid()
    process_start = _process_start_identity(pid)
    if process_start is None:
        raise RuntimeError(f"cannot read process birth identity for gateway pid={pid}")
    state = GatewayRuntimeState(
        pid=pid,
        process_start=process_start,
        config_path=str(config.source_path.resolve()),
        log_path=str(_default_gateway_log_path(config)),
    )
    _write_gateway_state(config, state)
    try:
        return runtime.run_forever()
    finally:
        restore()
        _remove_gateway_state(_gateway_state_path(config), expected=state)


def launch_gateway_in_background(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    spawn_process: BackgroundProcessFactory | None = None,
    wait_for_start: StartWaiter | None = None,
    im_service_url_override: str | None = None,
) -> BackgroundLaunchResult:
    """Start the gateway in a detached child and confirm its PID is live.

    Args:
        config_path: Operator-provided config path forwarded to the detached child.
        load_config: Config loader used to resolve lifecycle timing before spawning.
        spawn_process: Optional detached-child launcher override used by tests.
        wait_for_start: Optional PID/start confirmation waiter override used by tests.

    Returns:
        Detached process metadata once the child writes its PID and remains alive.

    Raises:
        RuntimeError: When the detached child exits or never confirms startup.
    """
    with _gateway_lifecycle_lock(config_path):
        return _launch_gateway_in_background_unlocked(
            config_path=config_path,
            load_config=load_config,
            spawn_process=spawn_process,
            wait_for_start=wait_for_start,
            im_service_url_override=im_service_url_override,
        )


def _launch_gateway_in_background_unlocked(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig],
    spawn_process: BackgroundProcessFactory | None,
    wait_for_start: StartWaiter | None,
    im_service_url_override: str | None,
) -> BackgroundLaunchResult:
    """Execute one background launch while the caller holds its lifecycle lock."""

    config = _load_runtime_config(
        config_path,
        load_config=load_config,
        im_service_url_override=im_service_url_override,
    )
    state_path = _gateway_state_path(config)
    existing_state = _read_gateway_state(state_path)
    if existing_state is not None:
        _assert_gateway_state_static(config, existing_state)
        signal_state = (
            _upgrade_legacy_gateway_state(config, existing_state.pid, existing_state)
            if existing_state.process_start is None
            else existing_state
        )
        if signal_state is not None and _gateway_process_matches(signal_state):
            raise GatewayStartupError(
                summary=f"gateway is already running (pid={existing_state.pid})",
                next_step="Run 'stop' to shut it down first, or 'restart' to replace it.",
            )
        _remove_gateway_state(state_path, expected=existing_state)
    else:
        legacy_pid = _read_legacy_gateway_pid(config)
        if legacy_pid is not None:
            legacy_state = _upgrade_legacy_gateway_state(config, legacy_pid, None)
            if legacy_state is not None and _gateway_process_matches(legacy_state):
                raise GatewayStartupError(
                    summary=f"gateway is already running (pid={legacy_pid})",
                    next_step="Run 'stop' to shut it down first, or 'restart' to replace it.",
                )
            _remove_legacy_gateway_pid(config, expected_pid=legacy_pid)

    log_path = _default_gateway_log_path(config)
    log_offset = log_path.stat().st_size if log_path.exists() else 0
    argv = _background_gateway_argv(
        config.source_path, im_service_url_override=im_service_url_override
    )
    launcher = spawn_process or _spawn_background_gateway_process
    start_waiter = wait_for_start or _wait_for_gateway_start
    process = launcher(argv, log_path)
    try:
        start_waiter(process, config, config.gateway.startup_timeout_seconds)
    except Exception as exc:
        _stop_background_process(
            process, timeout_seconds=config.gateway.shutdown_grace_seconds
        )
        hint = _read_log_last_error(log_path, offset=log_offset)
        summary = hint if hint else str(exc)
        raise GatewayStartupError(
            summary=summary,
            next_step=f"Check the log for details: tail -20 {log_path}",
        ) from exc
    result = BackgroundLaunchResult(
        pid=process.pid,
        log_path=log_path,
        im_service_url=config.im_service.url if config.im_service is not None else None,
    )
    published_state = _read_gateway_state(state_path)
    if published_state is None:
        _stop_background_process(
            process, timeout_seconds=config.gateway.shutdown_grace_seconds
        )
        raise GatewayStartupError(
            summary="gateway child did not publish lifecycle state",
            next_step=f"Check the log for details: tail -20 {log_path}",
        )
    _assert_gateway_state_static(config, published_state, expected_pid=process.pid)
    return result


def stop_gateway(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
) -> str:
    """Stop the background gateway associated with one config path.

    Args:
        config_path: Operator-provided config path used to resolve the runtime state file.
        load_config: Config loader used to derive the state file and shutdown timing.

    Returns:
        One operator-facing status line describing stop success, not-running, or stale state.

    Side Effects:
        Sends SIGTERM and possibly SIGKILL to the background gateway process and removes stale state.
    """
    with _gateway_lifecycle_lock(config_path):
        return _stop_gateway_unlocked(config_path=config_path, load_config=load_config)


def restart_gateway(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    spawn_process: BackgroundProcessFactory | None = None,
    wait_for_start: StartWaiter | None = None,
    im_service_url_override: str | None = None,
) -> BackgroundLaunchResult:
    """Stop and start one Gateway as a single serialized lifecycle operation.

    Args:
        config_path: Operator-provided config path identifying the lifecycle owner.
        load_config: Config loader shared by the stop and start phases.
        spawn_process: Optional detached-child launcher override used by tests.
        wait_for_start: Optional process-start confirmation override used by tests.
        im_service_url_override: Optional IM service URL forwarded to the new process.

    Returns:
        Metadata for the replacement background Gateway.

    Side Effects:
        Stops the owned Gateway, then launches its replacement while holding one lock.
    """
    with _gateway_lifecycle_lock(config_path):
        _stop_gateway_unlocked(config_path=config_path, load_config=load_config)
        return _launch_gateway_in_background_unlocked(
            config_path=config_path,
            load_config=load_config,
            spawn_process=spawn_process,
            wait_for_start=wait_for_start,
            im_service_url_override=im_service_url_override,
        )


def _stop_gateway_unlocked(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig],
) -> str:
    """Stop one Gateway while the caller holds its lifecycle lock."""

    config = load_config(config_path)
    state_path = _gateway_state_path(config)
    state = _read_gateway_state(state_path)
    if state is None:
        pid = _read_legacy_gateway_pid(config)
        if pid is None:
            return f"NOT RUNNING config={config.source_path.name} state={state_path}"
        success_target = f"pid_file={_legacy_gateway_pid_path(config)}"
        state_to_remove = None
    else:
        pid = state.pid
        _assert_gateway_state_static(config, state)
        success_target = f"state={state_path}"
        state_to_remove = state_path

    if state is None or state.process_start is None:
        signal_state = _upgrade_legacy_gateway_state(config, pid, state)
        if signal_state is None:
            _remove_legacy_gateway_pid(config, expected_pid=pid)
            if state_to_remove is not None:
                _remove_gateway_state(state_to_remove, expected=state)
            return f"STALE pid={pid} {success_target}"
    else:
        signal_state = state
    if not _gateway_process_matches(signal_state):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STALE pid={pid} {success_target}"

    if not _signal_gateway_process(signal_state, signal.SIGTERM):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STOPPED pid={pid} {success_target}"
    if _wait_for_gateway_exit(config, signal_state):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STOPPED pid={pid} {success_target}"
    if not _signal_gateway_process(signal_state, signal.SIGKILL):
        _clear_gateway_lifecycle(config, state_to_remove, signal_state)
        return f"STOPPED pid={pid} {success_target} forced=true"
    if not _wait_for_gateway_exit(config, signal_state):
        raise RuntimeError(
            f"gateway pid={pid} did not exit after SIGKILL; lifecycle state retained"
        )
    _clear_gateway_lifecycle(config, state_to_remove, signal_state)
    return f"STOPPED pid={pid} {success_target} forced=true"


def _wait_for_gateway_exit(config: LocalConfig, state: GatewayRuntimeState) -> bool:
    """Wait one shutdown grace interval for the original process instance to exit."""
    deadline = time.monotonic() + config.gateway.shutdown_grace_seconds
    while _gateway_process_matches(state):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(config.gateway.poll_interval_seconds, remaining))
    return True


def _clear_gateway_lifecycle(
    config: LocalConfig,
    state_path: Path | None,
    completed: GatewayRuntimeState,
) -> None:
    """Clear only lifecycle evidence that still names the completed instance."""
    if state_path is not None:
        _remove_gateway_state(state_path, expected=completed)
    _remove_legacy_gateway_pid(config, expected_pid=completed.pid)


class _KernelClientShim:
    """Adapt agent.sdk.Kernel to the kernel_client protocol.

    HeartbeatScheduler and InternalDispatchHandler use the old kernel_client
    interface (create_session/submit_message/append_message).  This shim
    bridges them to the in-process Kernel SDK.

    create_session is async so it can be properly awaited from the gateway's
    async event loop — run_until_complete on an already-running loop raises
    RuntimeError (refactor-387 M4 fix; previously the shim used that approach
    which silently prevented all heartbeat/cron runs from being submitted).
    """

    def __init__(
        self,
        kernel: "Kernel",
        *,
        agent_catalog: LiveAgentCatalog | None = None,
        session_binder: GatewaySessionBinder | None = None,
        product_default_model: str | None = None,
    ) -> None:
        self._kernel = kernel
        # refactor-406-M1 R6: per-agent config for building PromptSlots at
        # session-open (决策 8).  heartbeat/cron sessions look up the agent by
        # metadata["agent_id"] and assemble the PA prompt via prompt_for.
        self._agent_catalog = agent_catalog
        self._session_binder = session_binder
        # bugfix-429 决策2: product default model for the heartbeat/cron path.
        # Callers pass the agent's selected model (may be None); the shim falls
        # back to this so unattended runs use the same default as user turns.
        self._product_default_model = product_default_model

    async def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
        agent_snapshot: LiveAgentSnapshot | None = None,
    ) -> dict[str, object]:
        # Build per-session PromptSlots from the agent config (决策 8).  cron /
        # heartbeat sessions are direct (no group scenario), so only head/body/custom
        # slots populate; the tail (group context) stays empty.
        prompt = None
        enabled_tools = None
        features = None
        skills = None
        agent_id = (metadata or {}).get("agent_id")
        snapshot = agent_snapshot
        if snapshot is None:
            snapshot = (
                self._agent_catalog.get(agent_id)
                if self._agent_catalog is not None and isinstance(agent_id, str)
                else None
            )
        agent = snapshot.config if snapshot is not None else None
        if agent is not None:
            from personal_assistant.product import (  # noqa: PLC0415
                prompt_for,
                resolve_enabled_tools,
            )

            prompt = prompt_for(agent, scenario=metadata or {})
            enabled_tools = resolve_enabled_tools(agent)
            features = dict(getattr(agent, "features", {}) or {})
            # Match foreground session composition: a non-empty configured
            # subset restricts unattended sessions, while empty keeps the
            # existing SDK default-discovery compatibility.
            skills = list(agent.skills) if agent.skills else None
        session = await self._kernel.create_session(
            title=title,
            workspace_root=Path(workspace_root),
            metadata=metadata,
            prompt=prompt,
            skills=skills,
            enabled_tools=enabled_tools,
            features=features,
        )
        if snapshot is not None and self._session_binder is not None:
            self._session_binder.register_session_provenance(
                snapshot,
                kernel_session_id=session.session_id,
            )
        return {"session_id": session.session_id}

    async def create_agent_session(
        self,
        *,
        agent_snapshot: LiveAgentSnapshot,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Create an unattended session from one captured Agent revision."""

        return await self.create_session(
            workspace_root=workspace_root,
            product_id=product_id,
            title=title,
            metadata=metadata,
            agent_snapshot=agent_snapshot,
        )

    def submit_message(
        self,
        *,
        session_id: str,
        texts: list[str],
        image_urls: list[dict[str, object]] | None = None,
        workspace_root: str | None = None,
        origin: str | None = None,
        model: str | None = None,
        agent_id: str | None = None,
        **_kwargs: object,
    ) -> dict[str, object]:
        from agent.sdk import RunOrigin as _RunOrigin  # refactor-387-M4

        parts: list[dict] = [{"type": "text", "text": t} for t in texts]
        for img in image_urls or []:
            url = img.get("url")
            if isinstance(url, str) and url.strip():
                img_part: dict = {"type": "image", "image_url": url.strip()}
                mime = img.get("content_type")
                if isinstance(mime, str) and mime.strip():
                    img_part["mime_type"] = mime.strip()
                parts.append(img_part)
        # Map string origin → RunOrigin enum.
        # feat-394-M7 R5-1 fix: cron is an unattended isolated origin (no user present);
        # RunOrigin.SYSTEM does not exist — use per-origin explicit mapping.
        if origin == "heartbeat":
            run_origin: _RunOrigin = _RunOrigin.HEARTBEAT
        elif origin == "cron":
            run_origin = _RunOrigin.CRON
        else:
            run_origin = _RunOrigin.USER
        # bugfix-429 决策2 / fix-r1 #3: resolve via the shared helper — explicit
        # model (heartbeat passes agent.default_model) wins; else the agent looked
        # up by agent_id (cron); else the product default. The kernel holds none.
        snapshot = (
            self._agent_catalog.get(agent_id)
            if self._agent_catalog is not None and isinstance(agent_id, str)
            else None
        )
        resolved_agent = snapshot.config if snapshot is not None else None
        resolved_model = resolve_run_model(
            resolved_agent,
            product_default=self._product_default_model,
            explicit=model,
        )
        run_record = self._kernel.submit(
            session_id=session_id,
            parts=parts,
            origin=run_origin,
            workspace_root=Path(workspace_root) if workspace_root else None,
            model=resolved_model,
        )
        return {"run_id": run_record.run_id, "anchor_sequence": 0, "status": "queued"}

    def current_event_sequence(self) -> int:
        """Return the kernel's current max event sequence for use as a stream anchor.

        Delegated to Kernel.current_event_sequence() which reads the EventStreamHub
        without requiring access to agent.core internals.
        """
        return self._kernel.current_event_sequence()

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        message_id: str | None = None,
        workspace_root: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, object] | None = None,
        **_kwargs: object,
    ) -> dict[str, object]:
        self._kernel.append_message(
            session_id,
            role=role,
            content=content,
            message_id=message_id,
            workspace_root=Path(workspace_root) if workspace_root else None,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )
        return {"status": "appended"}

    def get_session(
        self, *, session_id: str, workspace_root: str | None = None
    ) -> dict[str, object]:
        return self._kernel.get_session(
            session_id,
            workspace_root=Path(workspace_root) if workspace_root else None,
        )

    def close(self) -> None:
        pass


def _make_prompt_preview_provider(kernel: Any) -> "PromptPreviewProvider":
    """Build a PromptPreviewProvider backed by Kernel.assemble_prompt_preview.

    sdk-fix-prompt-preview: in-process replacement for the removed kernel HTTP
    /v1/prompt-preview endpoint (refactor-387 M3 regression).  The returned
    callable matches PromptPreviewProvider signature so IMConnectionManager can
    call it transparently.

    Args:
        kernel: Assembled Kernel instance (agent.sdk.Kernel).

    Returns:
        Sync callable matching PromptPreviewProvider: (agent_id, workspace_root,
        features, custom_prompt, tool_ids, scenario, skill_ids) → dict.
    """
    from pathlib import Path as _Path  # noqa: PLC0415 — local import avoids circular risk

    def _provider(
        agent_id: str,
        workspace_root: str,
        features: dict,
        custom_prompt: "str | None",
        tool_ids: list,
        scenario: str,
        skill_ids: list = (),
    ) -> dict:
        # refactor-406-M1 R6 决策 8 (preview same-source): build PromptSlots with
        # the SAME prompt_for factory the runtime uses, from an "imaginary agent"
        # carrying the preview's feature flags / custom prompt.  Preview-seen ==
        # runtime-run; one byte-identity golden guards both.  Group scenario maps
        # to the prompt_for tail.
        from personal_assistant.product import prompt_for  # noqa: PLC0415

        feat = dict(features or {})
        scen_type = scenario or "direct"

        class _PreviewAgent:
            heartbeat_enabled = bool(feat.get("heartbeat", False))
            cron_enabled = bool(feat.get("cron_scheduling", False))

        _PreviewAgent.custom_prompt = custom_prompt  # type: ignore[attr-defined]
        prompt_scenario: dict = {"conversation_type": scen_type}
        prompt = prompt_for(_PreviewAgent(), scenario=prompt_scenario)

        return kernel.assemble_prompt_preview(
            workspace_root=_Path(workspace_root) if workspace_root else None,
            features=feat,
            tool_ids=list(tool_ids) if tool_ids else [],
            scenario=scen_type,
            skill_ids=list(skill_ids) if skill_ids else [],
            prompt=prompt,
            enabled_tools=list(tool_ids) if tool_ids else None,
        )

    return _provider  # type: ignore[return-value]


def build_runtime(config: LocalConfig) -> GatewayRuntime:
    """Construct the default long-running gateway runtime from parsed local config.

    refactor-387 M3: kernel is now in-process via agent.sdk.  No kernel child
    no independent Kernel process is spawned.
    """
    # refactor-406-M1 R6: PA assembles its kernel through the 2-layer SDK surface
    # via its own factory (personal_assistant.product).  PA imports only agent.sdk +
    # its own package — no product_profile / host_capabilities.
    from agent.sdk import LLMConfig
    from personal_assistant.builtin_skills.bootstrap import install_builtin_skills
    from personal_assistant.product import PA_SKILL_SEARCH_ROOTS, build_pa_kernel

    # PA does not supply can_use_tool: permission ask always parks on broker future
    # and is resolved by the user clicking Allow/Deny on the IM card via
    # kernel.submit_permission_decision.  Unattended origins (heartbeat/cron) short-circuit
    # before reaching ask via auto_mode_gate's unattended_fallback — they never park.
    #
    # The LLM catalog + active connection come from the Gateway config's ``llm:``
    # block (config.llm, an LLMConfigPayload) — NOT from_env — so the configured
    # default_model + provider catalog (incl. per-model extra_request_body like the
    # K2.6 thinking config) flow into build_kernel and the model registry.  decision 5:
    # build_kernel owns registry init internally from this LLMConfig.
    llm = LLMConfig.from_payload(config.llm)

    try:
        installed_builtin_skills = install_builtin_skills()
        if installed_builtin_skills:
            installed_names = ", ".join(sorted(installed_builtin_skills))
            _log.info(
                "installed built-in personal assistant skills: %s", installed_names
            )
    except Exception:  # noqa: BLE001
        _log.warning(
            "failed to install built-in personal assistant skills", exc_info=True
        )
    config, feishu_skill_config_changed = ensure_feishu_doc_skill_for_feishu_agents(
        config
    )
    if feishu_skill_config_changed:
        save_local_config(config, config.source_path)

    # CronServiceRegistry holds the per-agent CronExecutionService map + lifecycle
    # (set_gateway_loop / drain_all / register).  refactor-406 决策 9: the cron *tool*
    # holds this registry's mutable ``services`` dict directly and routes by agent_id —
    # no HostCapabilityDispatcher round-trip into the kernel.  Sharing the same dict
    # reference means services registered after build (post-kernel_shim) are visible to
    # the already-built tool closure.
    _cron_dispatcher = CronServiceRegistry()
    # The listener URL is a process-scoped capability. Construct its lifecycle owner
    # before the PA Kernel so send_message can resolve current_url on every tool call;
    # durable session metadata remains only a standalone/backward-compatible seed.
    _internal_dispatch_endpoint = InternalDispatchEndpoint()

    kernel = build_pa_kernel(
        llm=llm,
        cron_services=_cron_dispatcher.services,  # shared mutable map (决策 9)
        gateway_dispatch_url_provider=_internal_dispatch_endpoint.current_url,
        # can_use_tool=None: IM card flow; see submit_permission_decision.
    )

    agent_catalog = LiveAgentCatalog(config.agents)
    permission_response_handler = _build_permission_response_handler(kernel=kernel)

    runtime_dir = config.source_path.parent
    # Shared GroupContextStore for FeishuAdapter (non-mention group message buffer)
    # and InboundPipeline (context retrieval). Must be a single instance.
    group_context_store = GroupContextStore(
        db_path=runtime_dir / "group_context_buffer.sqlite3"
    )
    # The shim builds per-session PromptSlots/enabled_tools/features from agent config
    # (决策 8). The shared LiveAgentCatalog keeps heartbeat/cron session creation
    # current when config sync publishes a new Agent revision.
    channel_registry = _build_channel_registry(
        config.channels,
        dedup_db_path=runtime_dir / "relay_dedup.sqlite3",
        group_context_store=group_context_store,
        feishu_owner_open_id_binder=_build_feishu_owner_open_id_binder(config),
        feishu_permission_decision_callback=permission_response_handler,
    )
    outbound_router = OutboundRouter(channel_registry)
    # Use SQLite-backed store so kernel session mappings survive gateway restarts
    # (NodeGateway-SPEC §4.2).  Live session validation is owned by
    # GatewaySessionBinder via the in-process Kernel — no HTTP kernel client is needed.
    # Must be created before HeartbeatScheduler so the store can be injected for
    # tick-time canonical session lookup (feat-394 decision 3).
    session_store = PersistentSessionBindingStore(
        db_path=runtime_dir / "session_bindings.sqlite3"
    )
    session_binder = GatewaySessionBinder(
        catalog=agent_catalog,
        repository=session_store,
        kernel=kernel,
    )
    kernel_shim = _KernelClientShim(
        kernel,
        agent_catalog=agent_catalog,
        session_binder=session_binder,
        product_default_model=config.llm.default_model,
    )
    # feat-394 decision 3: canonical direct-chat kernel session store.
    # Updated by HeartbeatScheduler.tick() via session_store.find_direct_by_agent()
    # BEFORE each run submission (tick-time read, no reactive ack dependency).
    # This replaces the prior approach of populating from turn_start ack, which failed
    # for first-tick / restart / silent-polling scenarios (silent polls never ack → never fill).
    _canonical_session_store: dict[str, str] = {}
    reporter: UpstreamReporter | None = None
    im_connection_manager: IMConnectionManager | None = None
    im_bootstrap_client: _IMBootstrapClient | None = None
    im_config_sync_client: IMAgentConfigSync | None = None
    run_delivery_contexts = RunDeliveryContextStore()
    _owner_user_id = config.node.user_id or ""
    _gateway_internal_port = 0
    shadow_sync: IMShadowConversationSync | None = None
    image_resolver = ImageAttachmentResolver()

    def _send_external_reply(text: str, metadata: Mapping[str, str]) -> None:
        channel_name = metadata.get("channel_name") or ""
        target_chat_id = metadata.get("target_chat_id") or ""
        if not channel_name or not target_chat_id:
            return
        reply_metadata = {
            key: value
            for key, value in metadata.items()
            if key not in {"channel_name", "target_chat_id", "reply_thread_id"}
        }
        outbound_router.send_text(
            text=text,
            reply_context=ReplyContext(
                channel_name=channel_name,
                target_chat_id=target_chat_id,
                thread_id=metadata.get("reply_thread_id") or None,
                metadata=reply_metadata,
            ),
        )

    def _send_external_permission_request(
        request: Mapping[str, Any], metadata: Mapping[str, str]
    ) -> None:
        channel_name = metadata.get("channel_name") or ""
        target_chat_id = metadata.get("target_chat_id") or ""
        if not channel_name or not target_chat_id:
            return
        adapter = channel_registry.get(channel_name)
        sender = getattr(adapter, "send_permission_request", None)
        if not callable(sender):
            return
        sender(
            target_chat_id=target_chat_id,
            request=request,
            run_id=metadata.get("run_id") or "",
        )

    def _mark_external_permission_resolved(
        request_id: str, decision: str, metadata: Mapping[str, str]
    ) -> None:
        channel_name = metadata.get("channel_name") or ""
        if not channel_name:
            return
        adapter = channel_registry.get(channel_name)
        resolver = getattr(adapter, "mark_permission_resolved", None)
        if not callable(resolver):
            return
        resolver(request_id=request_id, decision=decision)

    def _on_agent_created(agent_id: str, workspace_root: Path) -> None:
        try:
            gateway_loop = asyncio.get_running_loop()
        except RuntimeError:
            gateway_loop = None
        _register_cron_service(agent_id, workspace_root, gateway_loop=gateway_loop)

    if config.im_service is not None:
        relay_adapter = channel_registry.get("web_relay")
        if not isinstance(relay_adapter, WebRelayAdapter):
            raise ValueError("im_service requires enabled web_relay channel")
        reporter = UpstreamReporter(
            node=config.node,
            agents=config.agents,
            send_frame=lambda _message_type, _payload: None,
            capabilities=build_runtime_capabilities(kernel),
        )
        # bugfix-424 (#127): derive dynamically-created agents' workspace from the
        # node's configured workspace_base so they land under the same isolation
        # root as preset agents (e.g. a worktree's `.gateway-workspace`) instead of
        # the hardcoded `~/nano-assistant/workspace` default. When workspace_base is
        # unset the factory stays None and the config sync keeps its legacy
        # default — existing deployments are unaffected.
        workspace_root_factory = _make_workspace_root_factory(
            config.node.workspace_base
        )
        im_config_sync_client = IMAgentConfigSync(
            base_url=config.im_service.url,
            token=config.im_service.token,
            agent_catalog=agent_catalog,
            session_binder=session_binder,
            local_config=config,
            reporter=reporter,
            workspace_root_factory=workspace_root_factory,
            global_skill_root=PA_SKILL_SEARCH_ROOTS[0],
            on_agent_created=_on_agent_created,
        )
        # Build a token_getter closure that auto-refreshes the access token on reconnect.
        # The auth client uses the IM HTTP base URL so it can reach /im/v1/auth/* endpoints.
        _auth_client = IMAuthClient(base_url=_im_http_base_url(config.im_service.url))
        _raw_token_getter = _make_token_getter(
            im_service=config.im_service,
            local_config=config,
            auth_client=_auth_client,
        )
        # feat-394-M3 fix: wrap token_getter so each successful token refresh also
        # propagates the new token to im_config_sync_client.  Without this, auto-bind
        # refreshes the token for WS reconnection but the sync client keeps the old
        # empty token, causing every sync_agent call to return 401.
        _sync_client_ref = im_config_sync_client

        async def _token_getter() -> str | None:
            token = await _raw_token_getter()
            if token is not None:
                _sync_client_ref.update_token(token)
            return token

        shadow_sync = IMShadowConversationSync(
            base_url=config.im_service.url,
            token_getter=_token_getter,
            owner_user_id=_owner_user_id,
        )
        image_resolver = ImageAttachmentResolver(
            fetcher=_build_attachment_fetcher(token_getter=_token_getter)
        )

        # M3: permission response handler is no longer wired — the SDK's can_use_tool
        # callback handles all permission decisions in-process (design decision 3).
        _im_sync_client = ConfigSyncClient(fetcher=im_config_sync_client.sync_agent)

        im_bootstrap_client = _IMBootstrapClient(
            base_url=_im_http_base_url(config.im_service.url),
            token=config.im_service.token,
            token_getter=_token_getter,
        )

        # feat-394-M12 决策 F: reconcile 回调——WS bind 完成后（含重连）拉全量 profile
        # 对账，消除漏推送导致的内存状态滞留。reconcile_all_agents 是同步 HTTP 调用，
        # 用 asyncio.to_thread 包装使其在 WS 事件循环中安全运行。
        # bugfix-446-M1 决策 3: node binding 并入 on_connected（移出启动关键路径）。
        # ensure_node_binding 对已绑定节点幂等（return None），其失败都是连接恢复期
        # 的瞬态条件或需人工处理的绑定问题。两者都不能阻断 agent reconcile；失败先
        # 以 degraded heartbeat 暴露给 IM，再让配置对账继续收敛。
        async def _reconcile_on_connect() -> None:
            try:
                await asyncio.to_thread(
                    im_bootstrap_client.ensure_node_binding,
                    node_id=config.node.node_id,
                )
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, GatewayStartupError):
                    summary = exc.summary
                    next_step = exc.next_step
                else:
                    summary = f"node {config.node.node_id} binding failed: {exc}"
                    next_step = None
                heartbeat_last_error = (
                    f"{summary}; next step: {next_step}" if next_step else summary
                )
                _log.warning("IM node binding failed during reconnect: %s", summary)
                _emit_gateway_feedback("ERROR", summary, next_step)
                if im_connection_manager is not None:
                    try:
                        await im_connection_manager.send_json(
                            "node.heartbeat",
                            reporter.send_heartbeat(
                                status="degraded", last_error=heartbeat_last_error
                            ),
                        )
                    except Exception as heartbeat_exc:  # noqa: BLE001
                        _log.warning(
                            "failed to send degraded IM heartbeat after binding failure: %s",
                            heartbeat_exc,
                        )
            memory_versions = {
                agent_id: ver
                for agent_id in (a.agent_id for a in config.agents)
                if (ver := _im_sync_client.latest_profile_version(agent_id)) is not None
            }
            await asyncio.to_thread(
                im_config_sync_client.reconcile_all_agents,
                memory_versions=memory_versions,
            )

    relay_lifecycle_callback = _build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: im_connection_manager,
        run_context_store=run_delivery_contexts,
        owner_user_id=_owner_user_id,
        channel_registry=channel_registry,
    )

    runtime_delivery_tasks = RuntimeDeliveryTaskTracker()
    _kernel_event_observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: im_connection_manager,
        run_context_store=run_delivery_contexts,
        external_reply_sender=_send_external_reply,
        external_permission_request_sender=_send_external_permission_request,
        external_permission_resolved_sender=_mark_external_permission_resolved,
        skill_created_handler=getattr(
            im_config_sync_client, "handle_skill_created", None
        ),
        task_tracker=runtime_delivery_tasks,
    )
    bg_reply_sender = _build_bg_reply_sender(
        im_connection_manager_factory=lambda: im_connection_manager,
        external_reply_sender=_send_external_reply,
    )
    session_event_callback = None
    if config.im_service is not None:
        # feat-349-M3: wire background session event callback so self_evolution_review
        # events published by background hooks reach IM as system/meta messages.
        session_event_callback = _build_session_event_callback(
            im_connection_manager_factory=lambda: im_connection_manager,
        )

    background_subscriptions = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=session_event_callback,
        bg_reply_sender=bg_reply_sender,
    )
    run_coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=session_binder,
        outbound_router=outbound_router,
        group_context_store=group_context_store,
        gateway_internal_port=_gateway_internal_port,
        gateway_dispatch_url_provider=_internal_dispatch_endpoint.current_url,
        product_default_model=config.llm.default_model,
        relay_lifecycle_callback=relay_lifecycle_callback,
        kernel_event_observer=_kernel_event_observer,
        bg_reply_sender=bg_reply_sender,
        background_subscriptions=background_subscriptions,
        image_resolver=image_resolver,
    )
    pipeline = InboundPipeline(
        agent_catalog=agent_catalog,
        run_coordinator=run_coordinator,
        group_context_store=group_context_store,
        route_config=InboundRouteConfig(),
        shadow_sync=shadow_sync,
    )
    inbound_dispatcher = InboundDispatcher(pipeline)

    # bugfix-402-M4 R4 / bugfix-402-M6: build per-agent CronExecutionService and
    # register with dispatcher. execute_fn captures only owners already constructed;
    # the runtime-delivery observer is supplied directly rather than read from a
    # heartbeat runner private field.
    #
    # bugfix-402 round-2: routing key changed from workspace_root to agent_id —
    # workspace_root has two data sources (local YAML vs IM-synced value from
    # reconcile_all_agents), causing lookup misses when the two differ.
    def _register_cron_service(
        agent_id: str,
        ws_root: Path,
        *,
        gateway_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Create a CronExecutionService for agent and register it with the dispatcher.

        bugfix-402-M6: extracted from the startup loop so handle_agent_create can
        call the same path for dynamically created agents.
        workspace_root must already be resolved (expanduser().resolve()).

        bugfix-402 round-2 code-review fix: gateway_loop is explicitly passed in
        rather than discovered via get_running_loop() at registration time.  When
        called from on_agent_created (inside the WS event loop), pass
        asyncio.get_running_loop() at the call site — not inside this function —
        so the loop reference comes from the caller's known context rather than
        an implicit environment that may not exist in all call paths.
        When called during static startup (before _run_until_shutdown sets the
        loop), pass None; set_gateway_loop() will inject the loop later.
        """
        # Skip if already registered (idempotent — reconcile may call multiple times).
        if _cron_dispatcher.resolve(agent_id) is not None:
            return
        runner = CronRunner(
            agent_id=agent_id,
            workspace_root=ws_root,
            kernel_client=kernel_shim,
            session_binder=session_binder,
            canonical_session_id_provider=lambda: _canonical_session_store.get(
                agent_id
            ),
        )
        stream_delivery = (
            CronRunStreamDelivery(
                kernel=kernel,
                owner_user_id=_owner_user_id,
                run_context_store=run_delivery_contexts,
                observer=_kernel_event_observer,
            )
            if _owner_user_id and _kernel_event_observer is not None
            else None
        )
        service = CronExecutionService(
            agent_id=agent_id,
            workspace_root=ws_root,
            runner=runner,
            stream_delivery=stream_delivery,
            gateway_loop=gateway_loop,
        )
        _cron_dispatcher.register(agent_id, service)
        # Converge stale accepted/running records from any previous crash so they
        # are never permanently in-progress.
        service.converge_stale_on_restart()

    # Create one CronExecutionService per configured agent and register with dispatcher.
    # bugfix-402-M6: use _register_cron_service so dynamic (handle_agent_create) and
    # static (startup) paths share the same key normalisation.
    for _agent_cfg in config.agents:
        _agent_ws_root = Path(_agent_cfg.workspace_root).expanduser().resolve()
        _register_cron_service(_agent_cfg.agent_id, _agent_ws_root)

    # feat-394-M3 CRITICAL-1 fix: wire cron tick into the unified polling runner.
    # bugfix-402-M4 R4: _cron_tick_for_agent now uses CronExecutionService.enqueue()
    # instead of building a submit_fn closure per tick.  Both scheduled and manual
    # triggers share the same execute chain via the dispatcher.
    async def _cron_tick_for_agent(agent_id: str) -> None:
        """Evaluate cron jobs for one agent and enqueue due runs via CronExecutionService.

        bugfix-402-M4 R4: replaces per-tick CronRunner+submit_fn with a call to the
        shared CronExecutionService.enqueue(trigger="scheduled") for each due job.
        CronScheduler still handles due-time computation and last_due_at persistence.
        """
        agent_snapshot = agent_catalog.get(agent_id)
        if agent_snapshot is None or not agent_snapshot.config.cron_enabled:
            return
        agent_cfg = agent_snapshot.config
        ws_root = Path(agent_cfg.workspace_root).expanduser().resolve()

        # bugfix-402 round-2: route by agent_id, not workspace_root.
        # workspace_root from pipeline may differ from the registered key when
        # reconcile_all_agents() rewrites it from IM (IM stores the original main
        # config path; the registered CronExecutionService may use a local/worktree
        # path).  agent_id is stable and unambiguous across all data sources.
        _service = _cron_dispatcher.resolve(agent_id)
        if _service is None:
            # Agent was dynamically registered after startup (IM config sync) without a
            # corresponding CronExecutionService.  Warn and skip — the service will be
            # created on the next Gateway restart when the agent appears in config.agents.
            _log.warning(
                "cron tick: no CronExecutionService for agent=%s; skipping",
                agent_id,
            )
            return

        job_store = CronJobStore(workspace_root=ws_root)
        # Per-agent state path so job last_due timestamps are isolated per agent.
        state_store = CronSchedulerStateStore(
            state_path=ws_root / _WCD / "cron" / "state.json"
        )

        # Use CronScheduler only for due-time computation; submit via CronExecutionService.
        async def _enqueue_via_service(*, agent_id: str, job: object) -> None:
            """Bridge CronScheduler.tick() → CronExecutionService.enqueue()."""
            job_id = getattr(job, "id", None)
            if not job_id:
                return
            _service.enqueue(job_id=job_id, trigger="scheduled")

        scheduler = CronScheduler(
            agent_id=agent_id,
            job_store=job_store,
            state_store=state_store,
            submit_fn=_enqueue_via_service,
        )
        await scheduler.tick()

    _heartbeat_scheduler = HeartbeatScheduler(
        agents=config.agents,
        kernel_client=kernel_shim,
        state_store=HeartbeatSchedulerStateStore(_default_heartbeat_state_path(config)),
        canonical_session_store=_canonical_session_store,
        agent_catalog=agent_catalog,
        session_binder=session_binder,
        is_session_busy=run_coordinator.is_session_busy,
    )
    heartbeat_runner = PollingHeartbeatRunner(
        scheduler=_heartbeat_scheduler,
        config=config.heartbeat,
        kernel=kernel if _owner_user_id else None,
        run_context_store=run_delivery_contexts if _owner_user_id else None,
        owner_user_id=_owner_user_id,
        agent_catalog=agent_catalog,
        kernel_event_observer=(_kernel_event_observer if _owner_user_id else None),
        cron_tick_fn=_cron_tick_for_agent,
    )

    if config.im_service is not None:
        assert reporter is not None
        assert im_config_sync_client is not None
        im_connection_manager = _build_im_connection_manager(
            config=config,
            relay_adapter=relay_adapter,
            reporter=reporter,
            heartbeat_runner=heartbeat_runner,
            sync_client=_im_sync_client,
            agent_config_provider=lambda agent_id: (
                im_config_sync_client.current_agent_payload(agent_id=agent_id)
            ),
            agent_capabilities_provider=lambda agent_id, workspace_root: (
                build_agent_capabilities_payload(
                    kernel,
                    workspace_root=workspace_root,
                    tool_allowlist=_resolve_agent_tool_allowlist(
                        im_config_sync_client, agent_id
                    ),
                )
            ),
            node_capabilities_provider=lambda: build_node_capabilities_payload(kernel),
            prompt_preview_provider=_make_prompt_preview_provider(kernel),
            agent_create_handler=im_config_sync_client.handle_agent_create,
            session_fork_handler=_build_session_fork_handler(
                kernel=kernel,
                session_binder=session_binder,
                channel_name=WebRelayAdapter.name,
            ),
            token_getter=_token_getter,
            permission_response_handler=permission_response_handler,
            on_connected=_reconcile_on_connect,
        )

    # bugfix-402-M3 R3: kernel is closed explicitly via GatewayRuntime(kernel=) and
    # its aclose() in the ordered shutdown phase (Decision 7). It must not be in
    # resource_closers — that list only holds lightweight sync cleanup (HTTP clients).
    closers: list[Callable[[], None]] = []
    if im_bootstrap_client is not None:
        closers.append(im_bootstrap_client.close)
    if im_config_sync_client is not None:
        closers.append(im_config_sync_client.close)
    internal_dispatch_handler = InternalDispatchHandler(
        im_connection_manager=im_connection_manager,
        kernel_client=kernel_shim,
        session_binder=session_binder,
    )
    return GatewayRuntime(
        config,
        channel_registry=channel_registry,
        heartbeat_runner=heartbeat_runner,
        im_connection_manager=im_connection_manager,
        on_inbound=inbound_dispatcher,
        resource_closers=tuple(closers),
        internal_dispatch_handler=internal_dispatch_handler,
        internal_dispatch_endpoint=_internal_dispatch_endpoint,
        kernel=kernel,
        cron_dispatcher=_cron_dispatcher,
        run_coordinator=run_coordinator,
        runtime_delivery_tasks=runtime_delivery_tasks,
        gateway_internal_port=_gateway_internal_port,
    )


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and execute the gateway process entry."""

    argv = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(
        description="Run personal assistant gateway runtime"
    )
    parser.add_argument(
        "--config",
        help="Path to local gateway config (defaults to ~/.nano-assistant/config.yaml)",
    )
    parser.add_argument(
        "--im-service-url",
        help="Override the upstream IM service base URL for this launch",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Keep the gateway attached to the current terminal for debugging and smoke tests",
    )
    parser.add_argument(
        "--auto-bind",
        action="store_true",
        help=(
            "Automatically confirm the IM node binding instead of opening a browser URL. "
            "Equivalent to setting NANO_MULTIAGENT_AUTO_BIND=1. "
            "Intended for worktree e2e scripts where no human can click the bind URL."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    stop_parser = subparsers.add_parser(
        "stop", help="Stop the current background gateway for one config"
    )
    stop_parser.add_argument(
        "--config",
        help="Path to local gateway config (defaults to ~/.nano-assistant/config.yaml)",
    )
    stop_parser.add_argument(
        "--im-service-url",
        help="Override the upstream IM service base URL for this launch",
    )
    restart_parser = subparsers.add_parser(
        "restart",
        help="Stop then start the background gateway (equivalent to stop + start)",
    )
    restart_parser.add_argument(
        "--config",
        help="Path to local gateway config (defaults to ~/.nano-assistant/config.yaml)",
    )
    restart_parser.add_argument(
        "--im-service-url",
        help="Override the upstream IM service base URL for this launch",
    )
    args = parser.parse_args(argv)
    command = args.command or "start"
    resolved_config_path = (
        str(Path(args.config).expanduser())
        if args.config
        else str(default_local_config_path())
    )
    if getattr(args, "auto_bind", False):
        os.environ["NANO_MULTIAGENT_AUTO_BIND"] = "1"
    try:
        if command == "stop":
            print(stop_gateway(config_path=resolved_config_path))
            return 0
        if command == "restart":
            result = restart_gateway(
                config_path=resolved_config_path,
                im_service_url_override=args.im_service_url,
            )
            _print_gateway_started(result)
            return 0
        if args.foreground:
            return run_gateway(
                config_path=resolved_config_path,
                im_service_url_override=args.im_service_url,
            )
        result = launch_gateway_in_background(
            config_path=resolved_config_path,
            im_service_url_override=args.im_service_url,
        )
        _print_gateway_started(result)
        return 0
    except GatewayStartupError as exc:
        _emit_gateway_feedback("ERROR", exc.summary, exc.next_step)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


def _coerce_factories(
    factories: RuntimeFactories | Mapping[str, Any] | None,
) -> RuntimeFactories:
    if factories is None:
        return RuntimeFactories()
    if isinstance(factories, RuntimeFactories):
        return factories
    load_config = factories.get("load_config", load_local_config)
    build_runtime_factory = factories.get("build_runtime")
    install_signal_handlers = factories.get("install_signal_handlers")
    return RuntimeFactories(
        load_config=load_config,
        build_runtime=build_runtime_factory,
        install_signal_handlers=install_signal_handlers,
    )


def _build_channel_registry(
    channels: tuple[ChannelConfig, ...],
    *,
    dedup_db_path: Path | None = None,
    group_context_store: GroupContextStore | None = None,
    feishu_owner_open_id_binder: Callable[[str, str], str | None] | None = None,
    feishu_permission_decision_callback: (
        Callable[[Mapping[str, object]], bool | None] | None
    ) = None,
) -> ChannelRegistry:
    has_feishu = any(ch.enabled and ch.name.startswith("feishu:") for ch in channels)
    if has_feishu and group_context_store is None:
        raise ValueError(
            "group_context_store is required when feishu channels are enabled"
        )
    registry = ChannelRegistry()
    for channel in channels:
        if not channel.enabled:
            continue
        if channel.name == "web_relay":
            dedup_store = None
            if dedup_db_path is not None:
                dedup_store = RelayDeduplicationStore(db_path=dedup_db_path)
            registry.register(WebRelayAdapter(dedup_store=dedup_store))
            continue
        # feat-447: feishu channels are named "feishu:<agent_id>"
        if channel.name.startswith("feishu:"):
            settings = channel.settings
            registry.register(
                FeishuAdapter(
                    name=channel.name,
                    app_id=settings["appId"],
                    app_secret=settings["appSecret"],
                    bot_open_id=settings.get("botOpenId"),
                    owner_open_id=settings.get("ownerOpenId"),
                    owner_open_id_binder=feishu_owner_open_id_binder,
                    permission_decision_callback=feishu_permission_decision_callback,
                    group_context_store=group_context_store,
                )
            )
            continue
        raise ValueError(f"unsupported channel adapter: {channel.name}")
    return registry


def _build_feishu_owner_open_id_binder(
    config: LocalConfig,
    *,
    save_config: Callable[[LocalConfig, str | Path], None] = save_local_config,
) -> Callable[[str, str], str | None]:
    """Bind missing Feishu ownerOpenId to the first real sender for an adapter."""
    lock = threading.Lock()

    def _bind(channel_name: str, sender_open_id: str) -> str | None:
        cleaned_sender = (
            sender_open_id.strip() if isinstance(sender_open_id, str) else ""
        )
        if not cleaned_sender:
            return None
        with lock:
            for channel in config.channels:
                if channel.name != channel_name or not channel.enabled:
                    continue
                if not channel.name.startswith("feishu:"):
                    return None
                existing = channel.settings.get("ownerOpenId")
                if isinstance(existing, str) and existing.strip():
                    return existing.strip()
                channel.settings["ownerOpenId"] = cleaned_sender
                source_path = getattr(config, "source_path", None)
                if source_path is not None:
                    try:
                        save_config(config, source_path)
                    except Exception:  # noqa: BLE001
                        _log.warning(
                            "failed to persist feishu ownerOpenId for channel %s",
                            channel_name,
                            exc_info=True,
                        )
                _log.info(
                    "bound feishu ownerOpenId from first inbound sender for channel %s",
                    channel_name,
                )
                return cleaned_sender
        return None

    return _bind


def _make_token_getter(
    *,
    im_service: IMServiceConfig,
    local_config: LocalConfig,
    auth_client: IMAuthClient,
    save_config: Callable[[LocalConfig, Path], None] = save_local_config,
) -> Callable[[], Awaitable[str | None]]:
    """Build an async closure that returns a fresh access token before each reconnect.

    Priority:
    1. If ``im_service.refresh_token`` is set, call ``IMAuthClient.refresh()``.
    2. If refresh fails and ``im_service.username`` + ``im_service.password`` are set,
       call ``IMAuthClient.login()`` as a fallback.
    3. If neither credential is available, return ``im_service.token`` unchanged
       (backwards-compatible behaviour for configs without auto-refresh).

    On success the returned (access_token, refresh_token) pair is persisted back into
    config.yaml so the new refresh token is available on the next process restart.

    Args:
        im_service: IM connectivity settings containing token credentials.
        local_config: Full gateway config used for ``save_config`` persistence path.
        auth_client: HTTP client implementing refresh/login against the IM auth API.
        save_config: Callable used to persist the updated config (injectable for tests).

    Returns:
        Async zero-argument callable that resolves to the latest access token or None.
    """
    # Mutable state: keep a local reference so token rotation is visible across calls
    # within the same gateway process lifetime.
    _state: dict[str, str | None] = {
        "refresh_token": im_service.refresh_token,
        "token": im_service.token,
    }
    _config_holder: list[LocalConfig] = [local_config]

    async def _getter() -> str | None:
        current_refresh = _state["refresh_token"]
        if current_refresh is not None:
            try:
                access, new_refresh = await auth_client.refresh(current_refresh)
                _state["token"] = access
                _state["refresh_token"] = new_refresh
                _persist(access, new_refresh)
                return access
            except IMAuthError:
                # Refresh token expired or revoked — fall through to credential login.
                pass

        username = im_service.username
        password = im_service.password
        if username and password:
            try:
                access, new_refresh = await auth_client.login(
                    username=username, password=password
                )
                _state["token"] = access
                _state["refresh_token"] = new_refresh
                _persist(access, new_refresh)
                return access
            except IMAuthError:
                pass

        # No dynamic auth configured or all methods failed — use the static token.
        return _state["token"]

    def _persist(access: str, new_refresh: str) -> None:
        current_cfg = _config_holder[0]
        old_im = current_cfg.im_service
        if old_im is None:
            return
        updated_im = IMServiceConfig(
            url=old_im.url,
            token=access,
            refresh_token=new_refresh,
            username=old_im.username,
            password=old_im.password,
        )
        new_cfg = replace(current_cfg, im_service=updated_im)
        _config_holder[0] = new_cfg
        save_config(new_cfg, new_cfg.source_path)

    return _getter


def _build_session_fork_handler(
    *,
    kernel: Any,
    session_binder: GatewaySessionBinder,
    channel_name: str,
) -> SessionForkHandler:
    """Build the gateway-side handler for IM-delegated session fork (feat-445-M1 决策 2).

    Resolves the source kernel session from the source conversation's binding, forks it
    at ``fork_point.message_id`` (kernel reproduces the source's as-of-M context view),
    and binds the new conversation to the forked session so its first inbound relay
    reuses it. Returns ``{ok, new_session_id}`` on success or ``{ok: False, error}`` —
    IM does the new-conversation rollback (decision 5), the gateway only reports.
    """

    async def _handle(payload: Mapping[str, object]) -> Mapping[str, object]:
        source_conversation_id = str(payload.get("source_conversation_id") or "")
        new_conversation_id = str(payload.get("new_conversation_id") or "")
        agent_id = str(payload.get("agent_id") or "")
        fork_point = payload.get("fork_point")
        message_id = (
            str(fork_point.get("message_id") or "")
            if isinstance(fork_point, Mapping)
            else ""
        )
        if not (
            source_conversation_id and new_conversation_id and agent_id and message_id
        ):
            return {"ok": False, "error": "fork request missing required fields"}

        source = session_binder.capture_binding_provenance(
            build_conversation_session_key(
                channel_name=channel_name,
                conversation_id=source_conversation_id,
                agent_id=agent_id,
            ),
            expected_agent_id=agent_id,
        )
        if source is None:
            external_source = str(payload.get("source_external_source") or "").strip()
            external_chat_id = str(payload.get("source_external_chat_id") or "").strip()
            if external_source and external_chat_id:
                source = session_binder.capture_binding_provenance(
                    build_external_session_key(
                        external_source=external_source,
                        external_chat_id=external_chat_id,
                        agent_id=agent_id,
                    ),
                    expected_agent_id=agent_id,
                )
        if source is None:
            return {"ok": False, "error": "source session binding not found"}

        try:
            new_session = await kernel.fork_session(
                source.binding.kernel_session_id,
                workspace_root=source.agent.config.workspace_root,
                up_to=message_id,
            )
        except Exception as exc:  # noqa: BLE001 — report to IM, which rolls back
            return {"ok": False, "error": str(exc)}

        bind_result = session_binder.bind_conversation(
            ConversationBindingRequest(
                channel_name=channel_name,
                conversation_id=new_conversation_id,
                agent_id=agent_id,
                kernel_session_id=new_session.session_id,
                guard=source.guard,
            ),
            source.agent,
        )
        if bind_result.status == "stale":
            return {
                "ok": False,
                "error": "agent config changed while session fork was running",
            }
        # feat-445-M2 #5: hand back the source→branch kernel-uuid re-stamp map so IM can
        # realign each copied bubble's kernel_message_id to the branch session's JSONL
        # uuids (else a recursive fork from a copied bubble 502s on the source uuid).
        return {
            "ok": True,
            "new_session_id": new_session.session_id,
            "id_map": dict(new_session.fork_id_map or {}),
        }

    return _handle


def _build_im_connection_manager(
    *,
    config: LocalConfig,
    relay_adapter: WebRelayAdapter,
    reporter: UpstreamReporter,
    heartbeat_runner: PollingHeartbeatRunner,
    sync_client: ConfigSyncClient | None = None,
    agent_config_provider: Callable[[str], dict[str, object] | None] | None = None,
    agent_capabilities_provider: Callable[[str, str], dict[str, object]] | None = None,
    node_capabilities_provider: Callable[[], dict[str, object]] | None = None,
    prompt_preview_provider: Callable[..., Any] | None = None,
    agent_create_handler: AgentCreateHandler | None = None,
    session_fork_handler: SessionForkHandler | None = None,
    token_getter: Callable[[], Awaitable[str | None]] | None = None,
    permission_response_handler: Callable[[Mapping[str, object]], bool] | None = None,
    on_connected: Callable[[], Awaitable[None]] | None = None,
) -> IMConnectionManager:
    im_service = config.im_service
    if im_service is None:
        raise ValueError("im_service configuration is required")
    return IMConnectionManager(
        config=IMConnectionConfig(url=im_service.url, token=im_service.token),
        reporter=reporter,
        relay_adapter=relay_adapter,
        sync_client=sync_client,
        heartbeat_trigger=lambda _agent_id, _reason: heartbeat_runner.request_tick(),
        agent_config_provider=agent_config_provider,
        agent_capabilities_provider=agent_capabilities_provider,
        node_capabilities_provider=node_capabilities_provider,
        prompt_preview_provider=prompt_preview_provider,
        agent_create_handler=agent_create_handler,
        session_fork_handler=session_fork_handler,
        token_getter=token_getter,
        connect=_connect_websocket,
        permission_response_handler=permission_response_handler,
        on_connected=on_connected,
    )


def _build_permission_response_handler(
    *,
    kernel: Any,
) -> Callable[[Mapping[str, object]], bool]:
    """Build handler that routes IM permission_response frames to the kernel.

    The frame carries ``request_id``, ``decision``, and an optional ``reason``.
    request_id is globally unique (assigned by auto_mode_gate at ask time), so
    no session lookup is required — the broker finds the pending future by id.
    """

    def _handler(body: Mapping[str, object]) -> bool:
        request_id = str(body.get("request_id") or "").strip()
        decision = str(body.get("decision") or "").strip()
        if not request_id or not decision:
            return False
        reason = str(body.get("reason") or "").strip()
        try:
            return bool(
                kernel.submit_permission_decision(
                    request_id=request_id,
                    decision=decision,
                    reason=reason,
                )
            )
        except Exception:  # noqa: BLE001 — side-effect; failure must not cascade
            return False

    return _handler


def _build_attachment_fetcher(
    *,
    token_getter: "Callable[[], Awaitable[str | None]]",
) -> "Callable[[str], Awaitable[bytes]]":
    """Build an async callable that downloads an IM attachment URL to raw bytes.

    bugfix-433 决策1: the inbound pipeline uses this to turn an IM-hosted HTTP image
    URL (unreachable to a remote provider) into a self-contained base64 data URL. The
    URL is the full attachment URL carried on the relay message; auth uses the live IM
    access token. Any HTTP / network error raises so the pipeline stops the turn and
    replies with the fixed "没能加载" message (决策5).
    """
    import httpx  # noqa: PLC0415

    async def _fetch(url: str) -> bytes:
        token = await token_getter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=_im_http_headers(token))
            response.raise_for_status()
            return response.content

    return _fetch


def _metadata_text(metadata: Mapping[str, object], *, key: str) -> str | None:
    value = metadata.get(key)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{field_name} must be a non-empty string")
    return value.strip()


def _default_heartbeat_state_path(config: LocalConfig) -> Path:
    return config.source_path.parent / "heartbeat-state.json"


def _default_gateway_log_path(config: LocalConfig) -> Path:
    return config.source_path.parent / "gateway.log"


def _extract_bind_token(bind_url: str) -> str | None:
    """Pull the ``token`` query parameter out of an IM bind URL.

    refactor-381: used by ``_IMBootstrapClient.ensure_node_binding`` when
    NANO_MULTIAGENT_AUTO_BIND=1 to programmatically confirm the binding.
    """

    parsed = urlparse(bind_url)
    qs = parse_qs(parsed.query)
    tokens = qs.get("token") or qs.get("bind_token") or []
    return tokens[0] if tokens else None


def _legacy_gateway_pid_path(config: LocalConfig) -> Path:
    """Return the pre-refactor PID file path used only during live migration.

    Returns:
        Path to ``gateway.pid`` inside the config's runtime directory.
    """
    return config.source_path.parent / "gateway.pid"


@contextmanager
def _gateway_lifecycle_lock(config_path: str | Path) -> Iterator[None]:
    """Serialize lifecycle operations for one resolved config across processes."""
    resolved = Path(config_path).expanduser().resolve()
    lock_path = resolved.parent / f".{resolved.name}.gateway-lifecycle.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _remove_legacy_gateway_pid(
    config: LocalConfig, *, expected_pid: int | None = None
) -> None:
    """Remove a legacy ``gateway.pid`` only while it names the expected process.

    Side Effects:
        Deletes the PID file; silently succeeds if the file is already gone.
    """
    if expected_pid is not None and _read_legacy_gateway_pid(config) != expected_pid:
        return
    with suppress(FileNotFoundError):
        _legacy_gateway_pid_path(config).unlink()


def _read_legacy_gateway_pid(config: LocalConfig) -> int | None:
    """Read a pre-refactor ``gateway.pid``, or ``None`` if absent/invalid.

    Returns:
        Integer PID when the file exists and contains a parseable integer; ``None`` otherwise.
    """
    pid_path = _legacy_gateway_pid_path(config)
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _process_start_identity(pid: int) -> str | None:
    """Read the OS process birth identity for one PID without signalling it."""
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        return None
    return " ".join(value.split())


def _process_command(pid: int) -> str | None:
    """Read the full live command for one PID without signalling it."""
    result = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
    )
    command = result.stdout.strip()
    return command if result.returncode == 0 and command else None


def _process_cwd(pid: int) -> Path | None:
    """Return the live process working directory when the OS exposes it."""
    proc_cwd = Path(f"/proc/{pid}/cwd")
    try:
        return proc_cwd.resolve(strict=True)
    except (FileNotFoundError, OSError):
        pass
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("n") and len(line) > 1:
            return Path(line[1:]).resolve()
    return None


def _legacy_gateway_command_matches(
    command: str, *, pid: int, config: LocalConfig
) -> bool:
    """Validate one legacy Gateway command by argv semantics, not formatting."""
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if (
        not any(
            argv[index : index + 2] == ["-m", "personal_assistant.main"]
            for index in range(max(0, len(argv) - 1))
        )
        or "--foreground" not in argv
    ):
        return False

    raw_config: str | None = None
    for index, value in enumerate(argv):
        if value == "--config" and index + 1 < len(argv):
            raw_config = argv[index + 1]
            break
        if value.startswith("--config="):
            raw_config = value.split("=", 1)[1]
            break
    if raw_config is None:
        candidate = default_local_config_path()
    else:
        candidate = Path(raw_config).expanduser()
        if not candidate.is_absolute():
            cwd = _process_cwd(pid)
            if cwd is None:
                return False
            candidate = cwd / candidate
    return candidate.resolve() == config.source_path.resolve()


def _upgrade_legacy_gateway_state(
    config: LocalConfig,
    pid: int,
    state: GatewayRuntimeState | None,
) -> GatewayRuntimeState | None:
    """Adopt a legacy PID only after its live command proves Gateway ownership."""
    before = _process_start_identity(pid)
    if before is None:
        return None
    command = _process_command(pid)
    after = _process_start_identity(pid)
    if after is None:
        return None
    if before != after:
        raise RuntimeError("legacy Gateway process changed; evidence retained")
    config_path = str(config.source_path.resolve())
    if command is None or not _legacy_gateway_command_matches(
        command, pid=pid, config=config
    ):
        raise RuntimeError("legacy Gateway ownership mismatch; evidence retained")
    upgraded = (
        replace(state, process_start=after)
        if state is not None
        else GatewayRuntimeState(
            pid=pid,
            process_start=after,
            config_path=config_path,
            log_path=str(_default_gateway_log_path(config)),
        )
    )
    if state is not None:
        _write_gateway_state(config, upgraded)
    _log.warning(
        "adopted legacy Gateway lifecycle evidence after live command verification"
    )
    return upgraded


def _assert_gateway_state_static(
    config: LocalConfig,
    state: GatewayRuntimeState,
    *,
    expected_pid: int | None = None,
) -> None:
    """Reject state that does not claim the selected PID and resolved config."""
    if (expected_pid is not None and state.pid != expected_pid) or Path(
        state.config_path
    ).resolve() != config.source_path.resolve():
        raise RuntimeError("gateway state does not match process and config")


def _gateway_process_matches(state: GatewayRuntimeState) -> bool:
    """Return whether the PID still names the original process birth."""
    return (
        state.process_start is not None
        and _process_start_identity(state.pid) == state.process_start
    )


def _signal_gateway_process(state: GatewayRuntimeState, sig: int) -> bool:
    """Signal the original Gateway instance after rechecking its PID birth."""
    if not _gateway_process_matches(state):
        return False
    try:
        pgid = os.getpgid(state.pid)
    except ProcessLookupError:
        return False
    if not _gateway_process_matches(state):
        return False
    try:
        if pgid == state.pid:
            os.killpg(pgid, sig)
        else:
            # Foreground launches do not own their shell's process group.
            os.kill(state.pid, sig)
    except ProcessLookupError:
        return False
    return True


def _gateway_state_path(config: LocalConfig) -> Path:
    return config.source_path.parent / ".gateway-state.json"


def _write_gateway_state(config: LocalConfig, state: GatewayRuntimeState) -> None:
    """Atomically publish the single lifecycle state document."""
    path = _gateway_state_path(config)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path: Path | None = Path(temp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            json.dump(asdict(state), stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if fd >= 0:
            os.close(fd)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _read_gateway_state(state_path: Path) -> GatewayRuntimeState | None:
    if not state_path.exists():
        return None
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return GatewayRuntimeState(
        pid=int(payload["pid"]),
        config_path=str(payload["config_path"]),
        log_path=str(payload["log_path"]),
        process_start=(
            str(payload["process_start"]).strip()
            if payload.get("process_start") is not None
            else None
        ),
    )


def _remove_gateway_state(
    state_path: Path, *, expected: GatewayRuntimeState | None = None
) -> None:
    if expected is not None and _read_gateway_state(state_path) != expected:
        return
    with suppress(FileNotFoundError):
        state_path.unlink()


def _resolve_agent_tool_allowlist(
    sync_client: "IMAgentConfigSync",
    agent_id: str,
) -> tuple[str, ...]:
    """Return the tool_allowlist for an agent from the live local config snapshot.

    Used when building the agent capabilities payload so feature toggle availability
    can be evaluated against the current tool allowlist (feat-379 decision 7).

    Args:
        sync_client: The config sync client that holds the current LocalConfig.
        agent_id: Agent whose tool_allowlist to look up.

    Returns:
        Tuple of allowed tool names; empty tuple when agent is not found.
    """
    payload = sync_client.current_agent_payload(agent_id=agent_id)
    if payload is None:
        return ()
    raw = payload.get("tool_allowlist")
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, str))


def _im_bootstrap_base_urls(url: str) -> tuple[str, ...]:
    return (_im_http_base_url(url),)


def _background_gateway_argv(
    config_path: Path, *, im_service_url_override: str | None = None
) -> list[str]:
    argv = [
        sys.executable,
        "-m",
        "personal_assistant.main",
        "--config",
        str(config_path),
    ]
    if isinstance(im_service_url_override, str) and im_service_url_override.strip():
        argv.extend(["--im-service-url", im_service_url_override.strip()])
    argv.append("--foreground")
    return argv


def _spawn_background_gateway_process(argv: list[str], log_path: Path) -> ProcessLike:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        return subprocess.Popen(
            argv,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
            close_fds=True,
        )


def _wait_for_gateway_start(
    process: ProcessLike, config: LocalConfig, timeout_seconds: float
) -> None:
    """Wait for the background Gateway child to publish complete lifecycle state.

    This is a process-start confirmation, not a runtime/channel readiness signal.
    ``run_gateway`` writes one atomic state document before entering ``run_forever``.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"gateway exited before startup confirmation with return code {return_code}"
            )
        state = _read_gateway_state(_gateway_state_path(config))
        if state is not None and state.process_start is not None:
            _assert_gateway_state_static(config, state, expected_pid=process.pid)
            if not _gateway_process_matches(state):
                raise RuntimeError(
                    "gateway exited before process identity confirmation"
                )
            return
        time.sleep(config.gateway.poll_interval_seconds or 0.2)
    raise RuntimeError(
        "timed out waiting for gateway startup confirmation "
        "(lifecycle state never appeared)"
    )


def _stop_background_process(process: ProcessLike, *, timeout_seconds: float) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    # Gateway owns the session created by start_new_session=True. Terminating the
    # process group also reaps channel/tool descendants owned by that Gateway.
    _kill_process_tree(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=timeout_seconds)
    except (TimeoutError, subprocess.TimeoutExpired):
        process.kill()
        _kill_process_tree(process.pid, signal.SIGKILL)
        with suppress(TimeoutError, subprocess.TimeoutExpired):
            process.wait(timeout=timeout_seconds)


def _kill_process_tree(pid: int, sig: int) -> None:
    """Send ``sig`` to the entire process group led by ``pid``; falls back to single pid.

    Gateway 后台启动时 ``start_new_session=True``，其 channel/tool 后代进程位于同一 pgid。
    killpg 一次性回收 Gateway 拥有的整棵进程树。
    pgid 拿不到(进程刚消失)时静默吞掉,让上层走 wait 路径决定下一步。
    """
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return


def _install_default_signal_handlers(
    runtime: GatewayRuntimeLike,
) -> SignalHandlerInstaller:
    def _installer() -> Callable[[], None]:
        if not isinstance(runtime, GatewayRuntime):
            return lambda: None
        if threading.current_thread() is not threading.main_thread():
            return lambda: None

        previous: dict[signal.Signals, Any] = {}

        def _handler(_signum: int, _frame: Any) -> None:
            runtime.request_shutdown()

        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, _handler)

        def _restore() -> None:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

        return _restore

    return _installer


async def _connect_websocket(url: str, headers: Mapping[str, str]) -> ClientConnection:
    return await websockets.connect(
        url, additional_headers=dict(headers), user_agent_header=None
    )


async def _await_background_task(task: asyncio.Task[None]) -> None:
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.TimeoutError:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def _consume_task_exception(task: asyncio.Task[object]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        _log.exception("background task raised unexpected exception: %s", exc)


if __name__ == "__main__":
    raise SystemExit(main())
