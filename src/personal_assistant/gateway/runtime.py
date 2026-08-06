"""Own the assembled Gateway runtime lifecycle and shutdown resource graph."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import (
    LocalConfig,
    WORKSPACE_CONFIG_DIRNAME as _WCD,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_dispatcher import InboundDispatcher
from personal_assistant.gateway.internal_dispatch import (
    InternalDispatchEndpoint,
    InternalDispatchHandler,
)
from personal_assistant.gateway.managed_channel_control import ManagedChannelControl
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.scheduler.cron_service_registry import CronServiceRegistry

_log = logging.getLogger("personal_assistant.gateway.runtime")


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


class GatewayStartupCollaborator(Protocol):
    """Describe a domain owner with synchronous Gateway-startup work."""

    def start(self) -> None:
        """Perform startup work after the Gateway event loop is available."""


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
        startup_collaborators: Domain owners whose startup work must finish after the
            event loop is live and before Gateway producers accept work.
        external_control_recovery: Drains durable external command confirmations after
            cached external channels are ready. It intentionally does not depend on IM
            connectivity, because a provider does not replay a command after restart.
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
        internal_dispatch_handler: InternalDispatchHandler | None = None,
        internal_dispatch_endpoint: InternalDispatchEndpoint | None = None,
        gateway_internal_port: int = 8089,
        kernel: object | None = None,
        cron_dispatcher: CronServiceRegistry | None = None,
        startup_collaborators: tuple[GatewayStartupCollaborator, ...] = (),
        managed_channel_control: ManagedChannelControl | None = None,
        run_coordinator: SessionRunCoordinator | None = None,
        runtime_delivery_tasks: RuntimeDeliveryTaskTracker | None = None,
        external_control_recovery: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._config = config
        self._channel_registry = channel_registry or ChannelRegistry()
        self._heartbeat_runner = heartbeat_runner
        self._im_connection_manager = im_connection_manager
        self._on_inbound = on_inbound or (lambda _message: None)
        self._im_watchdog_initial_seconds = im_watchdog_initial_seconds
        self._im_watchdog_max_seconds = im_watchdog_max_seconds
        self._resource_closers = resource_closers
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
        self._startup_collaborators = startup_collaborators
        self._managed_channel_control = managed_channel_control
        self._inbound_dispatcher = (
            on_inbound if isinstance(on_inbound, InboundDispatcher) else None
        )
        self._run_coordinator = run_coordinator
        self._runtime_delivery_tasks = runtime_delivery_tasks
        self._external_control_recovery = external_control_recovery
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
        for collaborator in self._startup_collaborators:
            collaborator.start()
        # Startup collaborators may create CronExecutionService instances. Inject the
        # live loop before any listener or channel producer can enqueue work.
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
            if self._managed_channel_control is not None:
                await self._managed_channel_control.start_cached()
            if self._external_control_recovery is not None:
                try:
                    await self._external_control_recovery()
                except Exception:  # noqa: BLE001
                    # Startup must remain available when a provider is briefly down.
                    # The durable intent remains pending and is retried on subsequent
                    # connection recovery or the next command delivery.
                    _log.exception("external control confirmation recovery failed")
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
            if self._managed_channel_control is not None:
                await self._run_shutdown_operation(
                    "managed channel close",
                    inner_deadline,
                    self._managed_channel_control.close,
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
                im_outbound_drain = getattr(self._im_connection_manager, "drain", None)
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


async def _await_background_task(task: asyncio.Task[None]) -> None:
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.TimeoutError:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
