"""Process entry for the personal assistant Node Gateway runtime."""

from __future__ import annotations

import argparse
import asyncio
import shlex
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from personal_assistant.channels.base import InboundMessage
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.client.kernel_api_client import KernelApiClient, KernelApiClientConfig
from personal_assistant.config.local_store import ChannelConfig, HeartbeatConfig, KernelConfig, LocalConfig, load_local_config
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline, RelayLifecycleUpdate
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.reporter.upstream_reporter import UpstreamReporter
from personal_assistant.scheduler.heartbeat_scheduler import HeartbeatScheduler, HeartbeatSchedulerStateStore
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager


ProcessLike = subprocess.Popen[Any]
ProcessFactory = Callable[[str], ProcessLike]
BackgroundProcessFactory = Callable[[list[str], Path], ProcessLike]
ReadyWaiter = Callable[[ProcessLike, LocalConfig, float], None]
Monotonic = Callable[[], float]
Sleep = Callable[[float], None]
AsyncConnect = Callable[[str, Mapping[str, str]], Awaitable[ClientConnection]]
SignalHandlerInstaller = Callable[[], Callable[[], None]]


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
        browser_opener: BrowserOpener = webbrowser.open,
        timeout_seconds: float = 5.0,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleep = time.sleep,
    ) -> None:
        self._client = client or httpx.Client(
            base_url=base_url,
            headers=_im_http_headers(token),
            timeout=timeout_seconds,
            trust_env=False,
        )
        self._browser_opener = browser_opener
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

        owner_id = self._wait_for_owner(node_id=node_id)
        if owner_id:
            return None
        response = self._client.post("/im/v1/bind", json={"action": "start", "node_id": node_id})
        response.raise_for_status()
        payload = response.json()
        bind_url = _require_text(payload.get("bind_url"), field_name="bind_url")
        self._browser_opener(bind_url, new=2, autoraise=True)
        return bind_url

    def close(self) -> None:
        """Release the owned HTTP client."""

        self._client.close()

    def _wait_for_owner(self, *, node_id: str) -> str:
        deadline = self._monotonic() + 5.0
        last_error: Exception | None = None
        while self._monotonic() <= deadline:
            try:
                return self._get_owner_id(node_id=node_id)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self._sleep(0.1)
        message = f"node {node_id} did not appear in IM bootstrap"
        if last_error is not None:
            raise RuntimeError(message) from last_error
        raise RuntimeError(message)

    def _get_owner_id(self, *, node_id: str) -> str:
        response = self._client.get("/im/v1/nodes")
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

    async def _run_loop(self) -> None:
        while not self._stop_requested:
            self._scheduler.tick()
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
    ) -> None:
        self._config = config
        self._process_manager = process_manager
        self._channel_registry = channel_registry or ChannelRegistry()
        self._heartbeat_runner = heartbeat_runner
        self._im_connection_manager = im_connection_manager
        self._on_inbound = on_inbound or (lambda _message: None)
        self._post_im_connect = post_im_connect
        self._resource_closers = resource_closers
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
                    await asyncio.to_thread(self._post_im_connect)
                im_task = asyncio.create_task(self._im_connection_manager.run_forever(), name="personal-assistant-im")
            self._ready_event.set()
            await asyncio.to_thread(self._shutdown_requested.wait)
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
    return BackgroundLaunchResult(
        pid=process.pid,
        health_url=f"{config.kernel.base_url}{config.kernel.health_path}",
        log_path=log_path,
    )


def build_runtime(config: LocalConfig) -> GatewayRuntime:
    """Construct the default long-running gateway runtime from parsed local config."""

    kernel_client = KernelApiClient(
        config=KernelApiClientConfig(
            base_url=config.kernel.base_url,
            token=config.kernel.token,
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

    parser = argparse.ArgumentParser(description="Run personal assistant gateway runtime")
    parser.add_argument("--config", required=True, help="Path to local node-config.yaml")
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Keep the gateway attached to the current terminal for debugging and smoke tests",
    )
    args = parser.parse_args(argv)
    try:
        if args.foreground:
            return run_gateway(config_path=args.config)
        result = launch_gateway_in_background(config_path=args.config)
        print(f"STARTED pid={result.pid} health_url={result.health_url} log={result.log_path}")
        return 0
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
            payload = reporter.send_delivery_receipt(
                relay_task_id=relay_task_id,
                delivery_status="completed",
                detail=update.reply_text,
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
