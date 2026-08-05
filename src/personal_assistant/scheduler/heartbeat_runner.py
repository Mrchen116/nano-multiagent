"""Run the Gateway heartbeat and cron polling loop."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from personal_assistant.config.local_store import HeartbeatConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.runtime_delivery.context import RunDeliveryContextStore
from personal_assistant.gateway.runtime_delivery.stream import (
    stream_run_to_completion as _stream_run_to_completion,
)
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatRunRecord,
    HeartbeatScheduler,
)

_log = logging.getLogger("personal_assistant.scheduler.heartbeat_runner")


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
        run_context_store: RunDeliveryContextStore | None = None,
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
            delivery = outcome.delivery
        except Exception:  # noqa: BLE001  — delivery failure does not disrupt gateway loop
            _hb_logger.exception(
                "heartbeat run delivery failed: agent=%s run_id=%s", agent_id, run_id
            )
            return

        if outcome.status != "completed":
            _hb_logger.warning(
                "heartbeat run reached non-success terminal: agent=%s run_id=%s "
                "status=%s error=%s",
                agent_id,
                run_id,
                outcome.status,
                outcome.error,
            )
            return

        # Silent heartbeat turns are removed by the Kernel conversation owner. The
        # run identity is stable even if later foreground messages reached the same
        # session before this consumer acquired its cleanup transaction.
        _was_silent = delivery is not None and delivery.resolved_conversation_id is None
        if _was_silent:
            try:
                await self._kernel.discard_run_messages(run_id)
            except Exception:  # noqa: BLE001
                _hb_logger.debug(
                    "heartbeat transcript trim failed (non-fatal): agent=%s run_id=%s",
                    agent_id,
                    run_id,
                )


def _consume_task_exception(task: asyncio.Task[object]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        _log.exception("background task raised unexpected exception: %s", exc)
