"""Process entry for the personal assistant Node Gateway runtime."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from personal_assistant.channels.base import InboundMessage
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.client.kernel_api_client import KernelApiClient, KernelApiClientConfig
from personal_assistant.config.local_store import (
    ChannelConfig,
    HeartbeatConfig,
    KernelConfig,
    LocalConfig,
    load_local_config,
    resolve_kernel_token,
)
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline, RelayLifecycleUpdate
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.reporter.upstream_reporter import UpstreamReporter
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
    HeartbeatTickSummary,
)
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager


ProcessLike = subprocess.Popen[Any]
ProcessFactory = Callable[[str], ProcessLike]
BackgroundProcessFactory = Callable[[list[str], Path], ProcessLike]
ReadyWaiter = Callable[[ProcessLike, LocalConfig, float], None]
Monotonic = Callable[[], float]
Sleep = Callable[[float], None]
AsyncConnect = Callable[[str, Mapping[str, str]], Awaitable[ClientConnection]]
SignalHandlerInstaller = Callable[[], Callable[[], None]]
BootstrapClientFactory = Callable[[str], httpx.Client]
FeedbackSink = Callable[[str, str, str | None], None]
_DEFAULT_LOCAL_IM_API_PORT = 8011


class GatewayStartupError(RuntimeError):
    """Represent one actionable startup failure shown to gateway operators.

    Args:
        summary: Human-readable failure summary.
        next_step: Optional concrete remediation step shown alongside the error.
    """

    def __init__(self, *, summary: str, next_step: str | None = None) -> None:
        cleaned_summary = summary.strip()
        cleaned_next_step = next_step.strip() if isinstance(next_step, str) and next_step.strip() else None
        super().__init__(cleaned_summary)
        self.summary = cleaned_summary
        self.next_step = cleaned_next_step


def _emit_gateway_feedback(level: str, summary: str, next_step: str | None = None) -> None:
    """Print one operator-facing gateway feedback line to stderr."""

    print(f"{level} {summary}", file=sys.stderr)
    if next_step is not None:
        print(f"NEXT {next_step}", file=sys.stderr)


class GatewayRuntimeLike(Protocol):
    """Describe the minimal lifecycle contract used by `run_gateway`."""

    def run_forever(self) -> int:
        """Run the gateway until shutdown and return the process exit code."""


class HeartbeatRunner(Protocol):
    """Describe the async lifecycle expected from the heartbeat runner wrapper."""

    async def start(self) -> None:
        """Start background scheduler ticking."""

    async def close(self) -> None:
        """Stop background scheduler ticking and wait for drain."""

    def build_product_reports(self) -> list[dict[str, object]]:
        """Return IM-facing heartbeat report payloads ready for `node.report`.

        Returns:
            Report payloads that should be forwarded to IM after heartbeat work has produced
            a user-visible result. Implementations may return an empty list when there is
            nothing new to publish.
        """


class IMConnectionManagerLike(Protocol):
    """Describe the async lifecycle required from the optional IM connector."""

    async def connect_once(self) -> None:
        """Establish the initial websocket connection and register the node."""

    async def run_forever(self) -> None:
        """Keep the websocket alive until close is requested."""

    async def close(self) -> None:
        """Close the websocket and stop reconnect attempts."""


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
        health_url: Ready-check URL operators can probe during follow-up troubleshooting.
        log_path: File receiving the detached child stdout/stderr stream.
    """

    pid: int
    health_url: str
    log_path: Path


@dataclass(frozen=True, slots=True)
class GatewayRuntimeState:
    """Persist the operator-facing metadata needed to locate one background gateway.

    Args:
        pid: Background gateway process id launched for this config.
        config_path: Absolute config path used for that process.
        health_url: Health endpoint associated with the launched gateway.
        log_path: Log file receiving the detached process output.
    """

    pid: int
    config_path: str
    health_url: str
    log_path: str


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

    def ensure_node_binding(self, *, node_id: str) -> str | None:
        """Open the bind URL when the upstream node still has no owner.

        Args:
            node_id: Gateway node id that was just registered over IM websocket.

        Returns:
            The opened bind URL for unbound nodes, or `None` when the node is already owned.

        Raises:
            RuntimeError: When IM bootstrap APIs do not expose the registered node.
        """

        owner_id, resolved_base_url = self._wait_for_owner(node_id=node_id)
        if owner_id:
            return None
        client = self._get_client(resolved_base_url)
        try:
            response = client.post("/im/v1/bind", json={"action": "start", "node_id": node_id})
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise GatewayStartupError(
                summary=f"node {node_id} could not start IM binding",
                next_step=f"Verify {resolved_base_url}/im/v1/bind is reachable, then rerun gateway.",
            ) from exc
        payload = response.json()
        bind_url = _require_text(payload.get("bind_url"), field_name="bind_url")
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
                    return self._get_owner_id(node_id=node_id, base_url=base_url), base_url
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self._sleep(0.1)
        checked_urls = ", ".join(f"{base_url}/im/v1/nodes" for base_url in self._base_urls)
        message = f"node {node_id} did not appear in IM bootstrap"
        next_step = f"Verify the IM node API is reachable at {checked_urls} and rerun gateway."
        if last_error is not None:
            raise GatewayStartupError(summary=message, next_step=next_step) from last_error
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


class GatewayProcessManager:
    """Manage the local agent kernel child process for the gateway.

    Args:
        config: Kernel process and health-probe settings loaded from local config.
        kernel_client: HTTP client used for readiness probes.
        process_factory: Factory used to spawn the kernel child process.
        monotonic: Monotonic clock source for timeout accounting.
        sleep: Sleep function used between readiness probes.
    """

    def __init__(
        self,
        *,
        config: KernelConfig,
        kernel_client: KernelApiClient,
        process_factory: ProcessFactory | None = None,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleep = time.sleep,
    ) -> None:
        self._config = config
        self._kernel_client = kernel_client
        self._process_factory = process_factory or _spawn_process
        self._monotonic = monotonic
        self._sleep = sleep
        self.process: ProcessLike | None = None

    def start_kernel_process(self) -> ProcessLike:
        """Spawn the local kernel child and wait until `/v1/health` reports ready.

        Returns:
            The spawned process handle once health probing succeeds.

        Raises:
            RuntimeError: When the kernel does not become healthy before timeout.

        Side Effects:
            Starts a subprocess and performs repeated HTTP health checks.
        """

        if self.process is not None:
            return self.process
        process = self._process_factory(self._config.command)
        self.process = process
        self._wait_for_health()
        return process

    def stop_kernel_process(self) -> None:
        """Terminate the managed kernel child, escalating to kill when needed.

        Side Effects:
            Sends terminate/kill signals to the managed child process.
        """

        process = self.process
        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=self._config.shutdown_grace_seconds)
        except (TimeoutError, subprocess.TimeoutExpired):
            process.kill()
        finally:
            self.process = None

    def _wait_for_health(self) -> None:
        deadline = self._monotonic() + self._config.startup_timeout_seconds
        last_error: Exception | None = None
        while self._monotonic() <= deadline:
            try:
                payload = self._kernel_client.health()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            else:
                if bool(payload.get("healthy")):
                    return
                last_error = RuntimeError(f"kernel reported unhealthy payload: {payload}")
            self._sleep(self._config.health_poll_interval_seconds)
        message = "kernel health check timed out"
        if last_error is not None:
            raise RuntimeError(message) from last_error
        raise RuntimeError(message)


class PollingHeartbeatRunner:
    """Run the existing heartbeat scheduler as a background tick loop.

    Args:
        scheduler: Existing scheduler implementation that evaluates `HEARTBEAT.md`.
        config: Local heartbeat runtime settings.
        sleep: Async sleep function used between tick passes.

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
    ) -> None:
        self._scheduler = scheduler
        self._config = config
        self._sleep = sleep
        self._stop_requested = False
        self._wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._product_reports: list[dict[str, object]] = []

    async def start(self) -> None:
        """Start background scheduler ticking exactly once."""

        if self._task is not None:
            return
        self._stop_requested = False
        self._wake_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="personal-assistant-heartbeat")

    async def close(self) -> None:
        """Stop the background loop and wait for the worker task to finish."""

        task = self._task
        if task is None:
            return
        self._stop_requested = True
        self._wake_event.set()
        await task
        self._task = None

    def request_tick(self) -> None:
        """Wake the loop so a manual IM-triggered tick can run promptly."""

        self._wake_event.set()

    def build_product_reports(self) -> list[dict[str, object]]:
        """Return heartbeat report payloads ready for IM publication.

        Returns:
            Newly accumulated heartbeat summaries and clears the local queue so the runtime
            publishes each heartbeat result to IM at most once.
        """
        payloads = list(self._product_reports)
        self._product_reports.clear()
        return payloads

    async def _run_loop(self) -> None:
        while not self._stop_requested:
            summary = self._scheduler.tick()
            self._product_reports.extend(_build_heartbeat_product_reports(summary))
            if self._stop_requested:
                break
            try:
                await asyncio.wait_for(self._wake_event.wait(), timeout=self._config.tick_interval_seconds)
            except TimeoutError:
                continue
            finally:
                self._wake_event.clear()


class _InboundDispatcher:
    """Bridge synchronous channel callbacks onto the async inbound pipeline."""

    def __init__(self, pipeline: InboundPipeline) -> None:
        self._pipeline = pipeline
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the runtime event loop used to execute inbound pipeline coroutines."""

        self._loop = loop

    def __call__(self, message: InboundMessage) -> None:
        """Schedule one inbound message on the runtime loop.

        Raises:
            RuntimeError: When called before the runtime loop is available.
        """

        loop = self._loop
        if loop is None:
            raise RuntimeError("gateway runtime loop is not ready")
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is loop:
            task = loop.create_task(self._pipeline.handle_inbound(message))
            task.add_done_callback(_consume_task_exception)
            return
        future = asyncio.run_coroutine_threadsafe(self._pipeline.handle_inbound(message), loop)
        future.add_done_callback(_consume_future_exception)


class GatewayRuntime:
    """Run the assembled Node Gateway process until shutdown is requested.

    Args:
        config: Parsed immutable local gateway config.
        process_manager: Kernel child-process lifecycle manager.
        channel_registry: Registry containing configured channel adapters.
        heartbeat_runner: Background heartbeat loop wrapper.
        im_connection_manager: Optional IM websocket connector.
        on_inbound: Shared synchronous inbound callback given to channel adapters.
        post_im_connect: Optional synchronous hook invoked after IM connect/register succeeds.
        resource_closers: Additional cleanup callables invoked after runtime shutdown.
    """

    def __init__(
        self,
        config: LocalConfig,
        process_manager: GatewayProcessManager,
        *,
        channel_registry: ChannelRegistry | None = None,
        heartbeat_runner: HeartbeatRunner | None = None,
        im_connection_manager: IMConnectionManagerLike | None = None,
        on_inbound: Callable[[InboundMessage], None] | None = None,
        post_im_connect: Callable[[], None] | None = None,
        resource_closers: tuple[Callable[[], None], ...] = (),
        feedback_sink: FeedbackSink = _emit_gateway_feedback,
    ) -> None:
        self._config = config
        self._process_manager = process_manager
        self._channel_registry = channel_registry or ChannelRegistry()
        self._heartbeat_runner = heartbeat_runner
        self._im_connection_manager = im_connection_manager
        self._on_inbound = on_inbound or (lambda _message: None)
        self._post_im_connect = post_im_connect
        self._resource_closers = resource_closers
        self._feedback_sink = feedback_sink
        self._ready_event = threading.Event()
        self._shutdown_requested = threading.Event()

    def wait_until_ready(self, timeout: float | None = None) -> bool:
        """Block until the runtime reaches ready state or timeout expires."""

        return self._ready_event.wait(timeout)

    def request_shutdown(self) -> None:
        """Request graceful shutdown from another thread or signal handler."""

        self._shutdown_requested.set()

    def run_forever(self) -> int:
        """Run the gateway until shutdown is requested.

        Returns:
            `0` after startup succeeds and graceful shutdown completes.
        """

        self._ready_event.clear()
        self._shutdown_requested.clear()
        return asyncio.run(self._run_until_shutdown())

    async def _run_until_shutdown(self) -> int:
        loop = asyncio.get_running_loop()
        if isinstance(self._on_inbound, _InboundDispatcher):
            self._on_inbound.bind_loop(loop)

        channels_started = False
        heartbeat_started = False
        im_connected = False
        im_task: asyncio.Task[None] | None = None
        try:
            self._process_manager.start_kernel_process()
            start_channels(self._channel_registry, self._on_inbound)
            channels_started = True
            if self._heartbeat_runner is not None:
                await self._heartbeat_runner.start()
                heartbeat_started = True
            if self._im_connection_manager is not None:
                await self._im_connection_manager.connect_once()
                im_connected = True
                if self._post_im_connect is not None:
                    try:
                        await asyncio.to_thread(self._post_im_connect)
                    except GatewayStartupError as exc:
                        await self._publish_startup_failure(exc)
                        raise
                await self._publish_heartbeat_product_reports()
                im_task = asyncio.create_task(self._im_connection_manager.run_forever(), name="personal-assistant-im")
            self._ready_event.set()
            await asyncio.to_thread(self._shutdown_requested.wait)
            await self._publish_heartbeat_product_reports()
            return 0
        finally:
            self._ready_event.clear()
            if heartbeat_started and self._heartbeat_runner is not None:
                await self._heartbeat_runner.close()
            if channels_started:
                stop_channels(self._channel_registry)
            if im_connected and self._im_connection_manager is not None:
                await self._im_connection_manager.close()
                if im_task is not None:
                    await _await_background_task(im_task)
            elif im_task is not None:
                im_task.cancel()
                with suppress(asyncio.CancelledError):
                    await im_task
            self._process_manager.stop_kernel_process()
            for closer in self._resource_closers:
                closer()

    async def _publish_startup_failure(self, exc: GatewayStartupError) -> None:
        self._feedback_sink("ERROR", exc.summary, exc.next_step)
        manager = self._im_connection_manager
        if manager is None or not manager.connected:
            return
        last_error = exc.summary if exc.next_step is None else f"{exc.summary} Next: {exc.next_step}"
        payload = {
            "node_id": self._config.node.node_id,
            "status": "degraded",
            "agent_count": len(self._config.agents),
            "last_error": last_error,
        }
        try:
            await manager.send_json("node.heartbeat", payload)
        except Exception:  # noqa: BLE001
            return

    async def _publish_heartbeat_product_reports(self) -> None:
        """Forward any newly produced heartbeat summaries to IM as user-visible reports.

        Notes:
            Heartbeat scheduling itself stays local to the gateway process. This bridge only
            ships already-prepared report payloads into the existing IM `node.report` path so
            the result becomes visible in the same product conversation surface as normal relay
            work.
        """
        manager = self._im_connection_manager
        runner = self._heartbeat_runner
        if manager is None or not manager.connected or runner is None:
            return
        build_reports = getattr(runner, "build_product_reports", None)
        if build_reports is None:
            return
        for payload in build_reports():
            try:
                await manager.send_json("node.report", payload)
            except Exception:  # noqa: BLE001
                return


def run_gateway(
    *,
    config_path: str | Path,
    factories: RuntimeFactories | Mapping[str, Any] | None = None,
) -> int:
    """Load config, build runtime, and execute the gateway entry flow.

    Args:
        config_path: YAML config file passed by the operator.
        factories: Optional factory overrides used by tests.

    Returns:
        Process exit code. `0` means the managed startup/shutdown sequence succeeded.
    """

    resolved_factories = _coerce_factories(factories)
    config = resolved_factories.load_config(config_path)
    builder = resolved_factories.build_runtime or build_runtime
    runtime = builder(config)
    restore_signal_handlers = resolved_factories.install_signal_handlers or _install_default_signal_handlers(runtime)
    restore = restore_signal_handlers()
    try:
        return runtime.run_forever()
    finally:
        restore()


def launch_gateway_in_background(
    *,
    config_path: str | Path,
    load_config: Callable[[str | Path], LocalConfig] = load_local_config,
    spawn_process: BackgroundProcessFactory | None = None,
    wait_for_ready: ReadyWaiter | None = None,
) -> BackgroundLaunchResult:
    """Start the gateway in a detached child and wait until it is ready.

    Args:
        config_path: Operator-provided config path forwarded to the detached child.
        load_config: Config loader used to resolve health-check details before spawning.
        spawn_process: Optional detached-child launcher override used by tests.
        wait_for_ready: Optional readiness waiter override used by tests.

    Returns:
        Detached process metadata once the child reaches ready state.

    Raises:
        RuntimeError: When the detached child exits or never becomes ready.
    """

    config = load_config(config_path)
    log_path = _default_gateway_log_path(config)
    argv = _background_gateway_argv(config.source_path)
    launcher = spawn_process or _spawn_background_gateway_process
    ready_waiter = wait_for_ready or _wait_for_gateway_ready
    process = launcher(argv, log_path)
    try:
        ready_waiter(process, config, config.kernel.startup_timeout_seconds)
    except Exception:
        _stop_background_process(process, timeout_seconds=config.kernel.shutdown_grace_seconds)
        raise
    result = BackgroundLaunchResult(
        pid=process.pid,
        health_url=f"{config.kernel.base_url}{config.kernel.health_path}",
        log_path=log_path,
    )
    _write_gateway_state(config, result)
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

    config = load_config(config_path)
    state_path = _gateway_state_path(config)
    state = _read_gateway_state(state_path)
    if state is None:
        return f"NOT RUNNING config={config.source_path.name} state={state_path}"
    if not _pid_is_running(state.pid):
        _remove_gateway_state(state_path)
        return f"STALE pid={state.pid} state={state_path}"
    try:
        os.kill(state.pid, signal.SIGTERM)
    except ProcessLookupError:
        _remove_gateway_state(state_path)
        return f"STALE pid={state.pid} state={state_path}"
    deadline = time.monotonic() + config.kernel.shutdown_grace_seconds
    while time.monotonic() <= deadline:
        if not _pid_is_running(state.pid):
            _remove_gateway_state(state_path)
            return f"STOPPED pid={state.pid} state={state_path}"
        time.sleep(config.kernel.health_poll_interval_seconds)
    os.kill(state.pid, signal.SIGKILL)
    _remove_gateway_state(state_path)
    return f"STOPPED pid={state.pid} state={state_path} forced=true"


def build_runtime(config: LocalConfig) -> GatewayRuntime:
    """Construct the default long-running gateway runtime from parsed local config."""

    kernel_token = resolve_kernel_token(config.kernel.token)
    kernel_client = KernelApiClient(
        config=KernelApiClientConfig(
            base_url=config.kernel.base_url,
            token=kernel_token,
            request_id=config.kernel.request_id,
            timeout_seconds=config.kernel.timeout_seconds,
        )
    )
    process_manager = GatewayProcessManager(config=config.kernel, kernel_client=kernel_client)
    channel_registry = _build_channel_registry(config.channels)
    outbound_router = OutboundRouter(channel_registry)
    heartbeat_runner = PollingHeartbeatRunner(
        scheduler=HeartbeatScheduler(
            agents=config.agents,
            kernel_client=kernel_client,
            state_store=HeartbeatSchedulerStateStore(_default_heartbeat_state_path(config)),
        ),
        config=config.heartbeat,
    )
    reporter: UpstreamReporter | None = None
    im_connection_manager: IMConnectionManager | None = None
    im_bootstrap_client: _IMBootstrapClient | None = None
    post_im_connect: Callable[[], None] | None = None
    if config.im_service is not None:
        relay_adapter = channel_registry.get("web_relay")
        if not isinstance(relay_adapter, WebRelayAdapter):
            raise ValueError("im_service requires enabled web_relay channel")
        reporter = UpstreamReporter(
            node=config.node,
            agents=config.agents,
            send_frame=lambda _message_type, _payload: None,
        )
        im_connection_manager = _build_im_connection_manager(
            config=config,
            relay_adapter=relay_adapter,
            reporter=reporter,
            heartbeat_runner=heartbeat_runner,
        )
        im_bootstrap_client = _IMBootstrapClient(
            base_url=_im_http_base_url(config.im_service.url),
            token=config.im_service.token,
        )
        post_im_connect = lambda: im_bootstrap_client.ensure_node_binding(node_id=config.node.node_id)
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=config.agents,
        outbound_router=outbound_router,
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        relay_lifecycle_callback=_build_relay_lifecycle_callback(
            reporter=reporter,
            im_connection_manager_factory=lambda: im_connection_manager,
        ),
    )
    inbound_dispatcher = _InboundDispatcher(pipeline)
    closers: list[Callable[[], None]] = [kernel_client.close]
    if im_bootstrap_client is not None:
        closers.append(im_bootstrap_client.close)
    return GatewayRuntime(
        config,
        process_manager,
        channel_registry=channel_registry,
        heartbeat_runner=heartbeat_runner,
        im_connection_manager=im_connection_manager,
        on_inbound=inbound_dispatcher,
        post_im_connect=post_im_connect,
        resource_closers=tuple(closers),
    )


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and execute the gateway process entry."""

    argv = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(description="Run personal assistant gateway runtime")
    parser.add_argument("--config", help="Path to local node-config.yaml for the default start command")
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Keep the gateway attached to the current terminal for debugging and smoke tests",
    )
    subparsers = parser.add_subparsers(dest="command")
    stop_parser = subparsers.add_parser("stop", help="Stop the current background gateway for one config")
    stop_parser.add_argument("--config", required=True, help="Path to local node-config.yaml")
    args = parser.parse_args(argv)
    command = args.command or "start"
    if command == "start" and not args.config:
        parser.error("the following arguments are required: --config")
    try:
        if command == "stop":
            print(stop_gateway(config_path=args.config))
            return 0
        if args.foreground:
            return run_gateway(config_path=args.config)
        result = launch_gateway_in_background(config_path=args.config)
        print(f"STARTED pid={result.pid} health_url={result.health_url} log={result.log_path}")
        return 0
    except GatewayStartupError as exc:
        _emit_gateway_feedback("ERROR", exc.summary, exc.next_step)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


def _coerce_factories(factories: RuntimeFactories | Mapping[str, Any] | None) -> RuntimeFactories:
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


def _build_channel_registry(channels: tuple[ChannelConfig, ...]) -> ChannelRegistry:
    registry = ChannelRegistry()
    for channel in channels:
        if not channel.enabled:
            continue
        if channel.name == "web_relay":
            registry.register(WebRelayAdapter())
            continue
        raise ValueError(f"unsupported channel adapter: {channel.name}")
    return registry


def _build_im_connection_manager(
    *,
    config: LocalConfig,
    relay_adapter: WebRelayAdapter,
    reporter: UpstreamReporter,
    heartbeat_runner: PollingHeartbeatRunner,
) -> IMConnectionManager:
    im_service = config.im_service
    if im_service is None:
        raise ValueError("im_service configuration is required")
    return IMConnectionManager(
        config=IMConnectionConfig(url=im_service.url, token=im_service.token),
        reporter=reporter,
        relay_adapter=relay_adapter,
        sync_client=ConfigSyncClient(),
        heartbeat_trigger=lambda _agent_id, _reason: heartbeat_runner.request_tick(),
        connect=_connect_websocket,
    )


def _build_relay_lifecycle_callback(
    *,
    reporter: UpstreamReporter | None,
    im_connection_manager_factory: Callable[[], IMConnectionManager | None],
):
    async def _callback(message: InboundMessage, update: RelayLifecycleUpdate) -> None:
        if reporter is None:
            return
        relay_task_id = _metadata_text(message.metadata, key="relay_task_id")
        if relay_task_id is None:
            return
        manager = im_connection_manager_factory()
        if manager is None or not manager.connected:
            return
        if update.phase == "accepted":
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay_task_id,
                delivery_status="sent",
                detail=f"run_id={update.run_id}" if update.run_id is not None else None,
            )
            await manager.send_json("node.delivery_receipt", payload)
            return
        if update.phase == "running":
            message_id = _metadata_text(message.metadata, key="message_id")
            if message_id is None or update.run_id is None:
                return
            payload = reporter.send_report(
                run_id=update.run_id,
                status="running",
                agent_id=update.agent_id,
                session_key=update.session_key,
                conversation_id=message.external_chat_id,
                message_id=message_id,
                summary=update.reply_text,
            )
            await manager.send_json("node.report", payload)
            return
        if update.phase == "completed":
            receipt_detail = update.reply_text
            if update.detail is not None:
                detail_parts = [receipt_detail] if receipt_detail is not None else []
                detail_parts.extend(f"{key}={value}" for key, value in update.detail.items())
                receipt_detail = " | ".join(detail_parts)
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay_task_id,
                delivery_status="completed",
                detail=receipt_detail,
            )
            await manager.send_json("node.delivery_receipt", payload)
            return
        if update.phase == "failed":
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay_task_id,
                delivery_status="failed",
                detail=update.error,
            )
            await manager.send_json("node.delivery_receipt", payload)

    return _callback


def _build_heartbeat_product_reports(summary: HeartbeatTickSummary) -> list[dict[str, object]]:
    """Translate heartbeat tick results into IM-visible `node.report` payloads.

    Args:
        summary: Scheduler tick result containing newly triggered heartbeat runs.

    Returns:
        One completed report payload per triggered heartbeat run. The payload is shaped to fit
        the existing IM `node.report` persistence path so heartbeat outcomes appear in the same
        product event stream as other agent execution updates.
    """
    payloads: list[dict[str, object]] = []
    for run in summary.triggered_runs:
        payloads.append(
            {
                "run_id": run.run_id,
                "status": "completed",
                "agent_id": run.agent_id,
                "session_key": f"{run.agent_id}::heartbeat",
                "conversation_id": f"heartbeat:{run.agent_id}",
                "message_id": run.run_id,
                "summary": f"Heartbeat complete for main agent {run.agent_id} at {run.due_at.isoformat()}.",
                "guidance": "Open your main agent thread in Web IM to review the latest heartbeat result.",
            }
        )
    return payloads


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


def _gateway_state_path(config: LocalConfig) -> Path:
    return config.source_path.parent / ".gateway-state.json"


def _write_gateway_state(config: LocalConfig, result: BackgroundLaunchResult) -> None:
    state = GatewayRuntimeState(
        pid=result.pid,
        config_path=str(Path(config.source_path).resolve()),
        health_url=result.health_url,
        log_path=str(result.log_path),
    )
    _gateway_state_path(config).write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")


def _read_gateway_state(state_path: Path) -> GatewayRuntimeState | None:
    if not state_path.exists():
        return None
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return GatewayRuntimeState(
        pid=int(payload["pid"]),
        config_path=str(payload["config_path"]),
        health_url=str(payload["health_url"]),
        log_path=str(payload["log_path"]),
    )


def _remove_gateway_state(state_path: Path) -> None:
    with suppress(FileNotFoundError):
        state_path.unlink()


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _im_http_headers(token: str | None) -> dict[str, str]:
    headers = {"User-Agent": "nano-multiagent-gateway-bootstrap"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _im_http_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme == "http":
        return f"http://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "https":
        return f"https://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "ws":
        return f"http://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "wss":
        return f"https://{parsed.netloc}{parsed.path}".rstrip("/")
    raise ValueError("IM URL must use http(s) or ws(s)")


def _im_bootstrap_base_urls(url: str) -> tuple[str, ...]:
    primary = _im_http_base_url(url)
    parsed = urlparse(primary)
    candidates = [primary]
    hostname = (parsed.hostname or "").strip().lower()
    if hostname in {"127.0.0.1", "localhost"} and parsed.port != _DEFAULT_LOCAL_IM_API_PORT:
        fallback_path = parsed.path.rstrip("/")
        fallback = f"{parsed.scheme}://{hostname}:{_DEFAULT_LOCAL_IM_API_PORT}{fallback_path}"
        candidates.append(fallback.rstrip("/"))
    unique: list[str] = []
    for candidate in candidates:
        normalized = candidate.rstrip("/")
        if normalized and normalized not in unique:
            unique.append(normalized)
    return tuple(unique)


def _background_gateway_argv(config_path: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "personal_assistant.main",
        "--config",
        str(config_path),
        "--foreground",
    ]


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


def _wait_for_gateway_ready(process: ProcessLike, config: LocalConfig, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() <= deadline:
        if process.poll() is not None:
            raise RuntimeError(f"gateway exited before ready with return code {process.poll()}")
        try:
            response = httpx.get(
                f"{config.kernel.base_url}{config.kernel.health_path}",
                timeout=1.0,
                trust_env=False,
            )
            payload = response.json()
            if isinstance(payload, dict) and bool(payload.get("healthy")):
                return
            last_error = RuntimeError(f"unexpected health payload: {payload}")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(config.kernel.health_poll_interval_seconds)
    if last_error is not None:
        raise RuntimeError("timed out waiting for gateway readiness") from last_error
    raise RuntimeError("timed out waiting for gateway readiness")


def _stop_background_process(process: ProcessLike, *, timeout_seconds: float) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout_seconds)
    except (TimeoutError, subprocess.TimeoutExpired):
        process.kill()
        with suppress(TimeoutError, subprocess.TimeoutExpired):
            process.wait(timeout=timeout_seconds)


def _install_default_signal_handlers(runtime: GatewayRuntimeLike) -> SignalHandlerInstaller:
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
    return await websockets.connect(url, additional_headers=dict(headers), user_agent_header=None)


async def _await_background_task(task: asyncio.Task[None]) -> None:
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.TimeoutError:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def _consume_task_exception(task: asyncio.Task[object]) -> None:
    with suppress(asyncio.CancelledError):
        task.result()


def _consume_future_exception(future: object) -> None:
    result = getattr(future, "result", None)
    if callable(result):
        with suppress(asyncio.CancelledError):
            result()


def _spawn_process(command: str) -> ProcessLike:
    return subprocess.Popen(shlex.split(command), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    raise SystemExit(main())
