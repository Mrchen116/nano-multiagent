from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import threading
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Protocol, Sequence

from agent.core.ids import make_run_id
from agent.core.utils.time import utc_now_iso as _utc_now_iso
from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.origin import RunOrigin
from agent.core.types import TokenUsage, TurnResult
from agent.core.hooks.context import HookContext
from agent.core.hooks.runner import HookRunner, log_hook_diagnostics
from agent.core.observability.logger import log_error, log_info
from agent.core.observability.tracing import bind_correlation, current_trace_id, span
from agent.core.session.manager import SessionManager
from agent.core.agent.run_control import RunController


class RegistryClosedError(RuntimeError):
    """Raised when submit() is called after the registry has been shut down.

    Consumers should treat this as a stable signal that the kernel is closing
    and no new work will be accepted.
    """


class _RegistryState(StrEnum):
    # Accepting new runs normally.
    OPEN = "open"
    # Draining: no new submissions; waiting for owned Tasks to reach terminal state.
    DRAINING = "draining"
    # Loop and thread have stopped.
    CLOSED = "closed"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    session_id: str
    status: RunStatus
    created_at: str
    updated_at: str
    trace_id: str | None = None
    turn_id: str | None = None
    stop_reason: str | None = None
    output_text: str | None = None
    error: Mapping[str, Any] | None = None
    usage: TokenUsage | None = None
    attempt: int | None = None
    next_delay: float | None = None
    cooldown: float | None = None
    last_error: Mapping[str, Any] | None = None
    origin: RunOrigin = RunOrigin.USER
    source_task_id: str | None = None
    # Session workspace root, threaded from the request so the stateless kernel
    # can locate the session JSONL on first load of this process lifetime.
    workspace_root: Path | None = None
    # Event-hub sequence captured at submit() time, immediately before this run's
    # first (QUEUED) status event is published.  Consumers stream with
    # ``after_sequence=start_sequence`` to receive exactly this run's events and
    # nothing from earlier turns — this is the single source of truth for "where
    # does this run begin in the session stream", so no consumer needs to dedup
    # replayed history (e.g. stale self_evolution_review) on every new turn.
    start_sequence: int = 0


class RuntimeRunner(Protocol):
    async def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        run_id: str | None = None,
        controller: RunController | None = None,
        workspace_root: Path | None = None,
    ):  # noqa: ANN001, ANN201
        ...


class EventHubLike(Protocol):
    def publish(
        self, *, event: str, session_id: str, data: dict[str, Any]
    ) -> object: ...

    def current_sequence(self) -> int: ...


class RunsRegistry:
    def __init__(
        self,
        *,
        runtime: RuntimeRunner,
        session_manager: SessionManager,
        event_hub: EventHubLike | None = None,
        hook_runner: HookRunner | None = None,
        drain_timeout_seconds: float = 30.0,
    ) -> None:
        self._runtime = runtime
        self._session_manager = session_manager
        self._event_hub = event_hub
        self._hook_runner = hook_runner
        self._lock = Lock()
        self._runs: dict[str, RunRecord] = {}
        self._controllers: dict[str, RunController] = {}
        # session_id → run_id for the currently-executing run (RUNNING state only).
        self._active_run_by_session: dict[str, str] = {}
        # bugfix-402-M3: owned Task handles so drain_async() can await each to
        # terminal state before stopping the loop.  Keyed by run_id; cleared in
        # the Task done-callback so the dict never outlives a completed Task.
        self._owned_tasks: dict[str, asyncio.Task] = {}
        # Lifecycle state: OPEN → DRAINING → CLOSED (see _RegistryState).
        self._state: _RegistryState = _RegistryState.OPEN
        # Signal that fires once all owned Tasks have completed (set inside loop).
        self._drain_done: asyncio.Future | None = None
        self._drain_timeout_seconds = drain_timeout_seconds
        # Dedicated async event-loop thread so that httpx.AsyncClient transport
        # is not torn down by per-call asyncio.run() (feat-335).
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: threading.Thread | None = None
        self._start_async_loop()

    def _start_async_loop(self) -> None:
        self._async_loop = asyncio.new_event_loop()
        self._async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._async_thread.start()

    def _run_async_loop(self) -> None:
        asyncio.set_event_loop(self._async_loop)
        self._async_loop.run_forever()

    def begin_shutdown(self) -> bool:
        """Atomically stop accepting new runs before the blocking drain starts.

        Returns:
            True while the registry still requires draining, or False when it
            was already fully closed.
        """
        with self._lock:
            if self._state is _RegistryState.CLOSED:
                return False
            self._state = _RegistryState.DRAINING
            return True

    def shutdown(self, *, grace_timeout_seconds: float | None = None) -> None:
        """Drain owned Tasks then stop the dedicated async loop.

        Transitions the registry OPEN → DRAINING → CLOSED.  All queued/running
        Tasks are waited (up to drain_timeout_seconds) before the loop stops.
        Calling shutdown() on an already-closed registry is a no-op.
        """
        if not self.begin_shutdown():
            return
        loop = self._async_loop
        if loop is None or not loop.is_running():
            with self._lock:
                self._state = _RegistryState.CLOSED
            return
        timeout = (
            grace_timeout_seconds
            if grace_timeout_seconds is not None
            else self._drain_timeout_seconds
        )
        drain_future: concurrent.futures.Future = concurrent.futures.Future()
        loop.call_soon_threadsafe(
            lambda: loop.create_task(
                self._drain_and_stop(drain_future, timeout), name="registry-drain"
            )
        )
        try:
            drain_future.result(timeout=timeout + 5.0)
        except concurrent.futures.TimeoutError:
            # Force-stop the loop if drain exceeded total wait budget.
            if loop.is_running():
                loop.call_soon_threadsafe(loop.stop)
        if self._async_thread is not None:
            self._async_thread.join(timeout=2.0)
        with self._lock:
            self._state = _RegistryState.CLOSED

    async def _drain_and_stop(
        self,
        done_future: "concurrent.futures.Future[None]",
        timeout_seconds: float,
    ) -> None:
        """Await owned Tasks then stop the event loop.

        Runs inside the registry's dedicated loop so Task awaits happen in the
        correct Context.  Cancels tasks that exceed the grace timeout.
        """
        try:
            with self._lock:
                owned = list(self._owned_tasks.items())
                controllers = dict(self._controllers)
                statuses = {
                    run_id: record.status for run_id, record in self._runs.items()
                }

            # Give each run a chance to exit in its own Task Context before the
            # hard timeout. Queued runs can become terminal immediately; active
            # runs observe abort at the next loop boundary.
            for run_id, _task in owned:
                controller = controllers.get(run_id)
                status = statuses.get(run_id)
                if controller is None:
                    continue
                if status is RunStatus.QUEUED:
                    controller.cancel()
                    controller.abort()
                    self._set_status(
                        run_id,
                        status=RunStatus.CANCELLED,
                        stop_reason="shutdown",
                        only_if={RunStatus.QUEUED, RunStatus.RUNNING},
                    )
                elif status is RunStatus.RUNNING:
                    controller.abort()

            if owned:
                tasks = [task for _run_id, task in owned]
                _done, pending = await asyncio.wait(
                    tasks,
                    timeout=timeout_seconds,
                )
                if pending:
                    forced = [
                        (run_id, task) for run_id, task in owned if task in pending
                    ]
                    for _run_id, task in forced:
                        task.cancel()
                    await asyncio.gather(
                        *(task for _run_id, task in forced),
                        return_exceptions=True,
                    )
                    for run_id, _task in forced:
                        self._mark_shutdown_cancelled(run_id)
                        self._recover_shutdown_cancelled_session(run_id)
        finally:
            self._async_loop.stop()
            if not done_future.done():
                done_future.set_result(None)

    def _mark_shutdown_cancelled(self, run_id: str) -> RunRecord | None:
        """Persist a terminal state for a Task force-cancelled during shutdown."""
        return self._set_status(
            run_id,
            status=RunStatus.CANCELLED,
            stop_reason="shutdown",
            error={
                "code": "run_cancelled_on_shutdown",
                "message": "run was cancelled while the kernel was shutting down",
                "retryable": False,
            },
            only_if={RunStatus.QUEUED, RunStatus.RUNNING},
        )

    def _recover_shutdown_cancelled_session(self, run_id: str) -> None:
        """Close orphaned tool calls left by a force-cancelled run."""
        record = self.get(run_id)
        if record is None:
            return
        try:
            self._session_manager.prepare_transcript_for_run(
                record.session_id,
                reason="shutdown",
                workspace_root=record.workspace_root,
            )
            invalidate = getattr(self._runtime, "invalidate_session_cache", None)
            if callable(invalidate):
                invalidate(record.session_id)
        except Exception as exc:  # noqa: BLE001
            log_error(
                "run_shutdown_recovery_failed",
                run_id=run_id,
                session_id=record.session_id,
                error=str(exc),
            )

    def _on_task_done(self, run_id: str) -> None:
        """Remove a completed Task from the owned-tasks map (done-callback)."""
        with self._lock:
            self._owned_tasks.pop(run_id, None)

    def submit(
        self,
        *,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
        origin: RunOrigin = RunOrigin.USER,
        source_task_id: str | None = None,
        trace_id: str | None = None,
        workspace_root: Path | None = None,
    ) -> RunRecord:
        """Submit a turn for execution.

        ``workspace_root`` is threaded from the request so the stateless kernel
        can locate the session JSONL; it is required (in production) for the
        existence check below and for the runtime's first load of the session.
        """
        # Fast rejection avoids session I/O once shutdown has begun. The state is
        # checked again at record insertion because shutdown may race this work.
        with self._lock:
            if self._state is not _RegistryState.OPEN:
                raise RegistryClosedError(
                    "registry is shutting down; no new runs will be accepted"
                )
        if (
            self._session_manager.get_session(session_id, workspace_root=workspace_root)
            is None
        ):
            raise ValueError(f"session does not exist: {session_id}")
        if not parts:
            raise ValueError("empty input parts are not allowed")

        run_id = make_run_id()
        now = _utc_now_iso()
        resolved_trace_id = trace_id or current_trace_id()
        # Snapshot the hub position before publishing this run's first event, so
        # the run carries its own stream origin (see RunRecord.start_sequence).
        start_sequence = (
            self._event_hub.current_sequence() if self._event_hub is not None else 0
        )
        record = RunRecord(
            run_id=run_id,
            session_id=session_id,
            status=RunStatus.QUEUED,
            created_at=now,
            updated_at=now,
            trace_id=resolved_trace_id,
            origin=origin,
            source_task_id=source_task_id,
            workspace_root=workspace_root,
            start_sequence=start_sequence,
        )
        with self._lock:
            if self._state is not _RegistryState.OPEN:
                raise RegistryClosedError(
                    "registry is shutting down; no new runs will be accepted"
                )
            self._runs[run_id] = record
            self._controllers[run_id] = RunController()
        self._persist_run_status_entry(record)
        self._publish_run_status_event(record)
        log_info(
            "run_submitted",
            run_id=run_id,
            session_id=session_id,
            trace_id=resolved_trace_id,
        )

        normalized_parts = [dict(part) for part in parts]
        # Capture the caller's Context now (at submit() time) and pass it to the
        # Task so that bind_correlation's ContextVar set/reset both happen inside
        # the same copied Context.  Without this, ensure_future schedules the
        # coroutine in the background thread's default Context, and
        # _context.reset(token) raises "token was created in a different Context"
        # (Issue #3, refactor-387 sdk-fix-r3).
        ctx = contextvars.copy_context()

        # bugfix-402-M3: register Task handle so drain_async() can await it.
        # The done-callback removes the Task from _owned_tasks when it finishes.
        def _schedule_and_register() -> None:
            with self._lock:
                if self._state is not _RegistryState.OPEN:
                    task = None
                else:
                    task = self._async_loop.create_task(
                        self._run_worker_async(
                            run_id,
                            session_id,
                            normalized_parts,
                            resolved_trace_id,
                            workspace_root=workspace_root,
                            origin=origin,
                        ),
                        context=ctx,
                        name=f"run-{run_id}",
                    )
                    self._owned_tasks[run_id] = task
            if task is None:
                self._mark_shutdown_cancelled(run_id)
                return
            task.add_done_callback(lambda _t: self._on_task_done(run_id))

        with self._lock:
            if self._state is _RegistryState.OPEN:
                self._async_loop.call_soon_threadsafe(_schedule_and_register)
                scheduled = True
            else:
                scheduled = False
        if not scheduled:
            self._mark_shutdown_cancelled(run_id)
        return record

    def get_event_loop(self) -> asyncio.AbstractEventLoop | None:
        """Return the dedicated async event loop used by this registry."""
        return self._async_loop

    def get_active_run_id(self, session_id: str) -> str | None:
        """Return the run_id of the currently-executing run for a session, or None."""
        with self._lock:
            return self._active_run_by_session.get(session_id)

    def interrupt(self, session_id: str) -> str | None:
        """Signal force interrupt for the active run of a session.

        Returns the run_id if an active run was found and signalled, None otherwise.
        """
        with self._lock:
            run_id = self._active_run_by_session.get(session_id)
            controller = self._controllers.get(run_id) if run_id else None
        if controller is not None:
            controller.abort()
            log_info("run_interrupted", run_id=run_id, session_id=session_id)
            return run_id
        return None

    def inject_pending_message(self, session_id: str, message: LLMMessage) -> bool:
        """Enqueue a message for round-boundary injection into the active run.

        Returns True if the message was enqueued, False if no active run exists
        or the run is already being interrupted.
        """
        with self._lock:
            run_id = self._active_run_by_session.get(session_id)
            controller = self._controllers.get(run_id) if run_id else None
        if controller is not None and not controller.is_aborted:
            controller.enqueue_message(message)
            return True
        return False

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return None
            return replace(record)

    def cancel(self, run_id: str) -> RunRecord | None:
        with self._lock:
            current = self._runs.get(run_id)
            controller = self._controllers.get(run_id)
        if controller is not None:
            controller.cancel()
        if current is None:
            return None
        if current.status in _TERMINAL_STATUSES:
            return replace(current)
        return self._set_status(
            run_id,
            status=RunStatus.CANCELLED,
            stop_reason="cancelled",
            only_if={RunStatus.QUEUED, RunStatus.RUNNING},
        )

    async def _run_worker_async(
        self,
        run_id: str,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
        trace_id: str | None,
        *,
        workspace_root: Path | None = None,
        origin: RunOrigin = RunOrigin.USER,
    ) -> None:
        # Transient LLM retry is handled inside AgentLoop._generate_with_retry().
        # _run_worker executes the turn exactly once; any ModelError that reaches
        # this layer (including retryable=True exhausted by the loop) is terminal.
        with bind_correlation(session_id=session_id, trace_id=trace_id):
            started = self._set_status(
                run_id,
                status=RunStatus.RUNNING,
                only_if={RunStatus.QUEUED},
            )
            if started is None or started.status is not RunStatus.RUNNING:
                return
            log_info("run_started", run_id=run_id)

            with self._lock:
                controller = self._controllers.get(run_id)
                if controller is not None and not controller.is_cancelled:
                    self._active_run_by_session[session_id] = run_id

            if self._is_cancelled(run_id):
                with self._lock:
                    self._active_run_by_session.pop(session_id, None)
                return
            try:
                with span(
                    "RunsRegistry.run_worker", run_id=run_id, session_id=session_id
                ):
                    result = await self._runtime.run(
                        session_id,
                        parts,
                        stream=False,
                        run_id=run_id,
                        controller=controller,
                        workspace_root=workspace_root,
                        origin=origin,
                    )
            except TimeoutError as exc:
                await self._mark_timed_out_async(run_id, message=str(exc))
                return
            except Exception as exc:  # noqa: BLE001
                await self._mark_failed_async(run_id, message=str(exc))
                return
            finally:
                with self._lock:
                    if self._active_run_by_session.get(session_id) == run_id:
                        self._active_run_by_session.pop(session_id, None)
            if getattr(result, "stop_reason", None) == "aborted":
                await self._mark_aborted_async(run_id, source="priority_now")
            else:
                self._mark_completed(run_id, turn_result=result)
            # Race safety: background tasks that completed while this run was
            # still in _active_run_by_session may have injected messages that
            # were never consumed. Drain them and start a continuation run.
            if controller is not None:
                stranded = controller.drain_pending()
                if stranded:
                    self.submit(
                        session_id=session_id,
                        parts=[
                            {"type": "text", "text": msg.content} for msg in stranded
                        ],
                        origin=RunOrigin.BACKGROUND_TASK,
                        workspace_root=workspace_root,
                    )

    def _set_status(
        self,
        run_id: str,
        *,
        status: RunStatus,
        turn_id: str | None = None,
        stop_reason: str | None = None,
        output_text: str | None = None,
        error: Mapping[str, Any] | None = None,
        usage: TokenUsage | None = None,
        attempt: int | None = None,
        next_delay: float | None = None,
        cooldown: float | None = None,
        last_error: Mapping[str, Any] | None = None,
        only_if: set[RunStatus] | None = None,
    ) -> RunRecord | None:
        with self._lock:
            current = self._runs.get(run_id)
            if current is None:
                return None
            if only_if is not None and current.status not in only_if:
                return replace(current)
            updated = replace(
                current,
                status=status,
                updated_at=_utc_now_iso(),
                turn_id=turn_id,
                stop_reason=stop_reason,
                output_text=output_text,
                error=error,
                usage=usage,
                attempt=attempt,
                next_delay=next_delay,
                cooldown=cooldown,
                last_error=last_error,
            )
            self._persist_run_status_entry(updated)
            self._runs[run_id] = updated
        self._publish_run_status_event(updated)
        return updated

    def _is_cancelled(self, run_id: str) -> bool:
        with self._lock:
            current = self._runs.get(run_id)
            controller = self._controllers.get(run_id)
        if current is not None and current.status is RunStatus.CANCELLED:
            return True
        return controller is not None and controller.is_cancelled

    def _mark_completed(
        self, run_id: str, *, turn_result: TurnResult
    ) -> RunRecord | None:
        updated = self._set_status(
            run_id,
            status=RunStatus.COMPLETED,
            turn_id=turn_result.turn_id,
            stop_reason=turn_result.stop_reason,
            output_text=_extract_run_output_text(turn_result),
            error=None,
            usage=turn_result.usage,
            only_if={RunStatus.RUNNING},
        )
        if updated is not None and updated.status is RunStatus.COMPLETED:
            log_info(
                "run_completed",
                run_id=run_id,
                session_id=updated.session_id,
                turn_id=turn_result.turn_id,
                trace_id=updated.trace_id,
            )
        return updated

    async def _mark_failed_async(
        self, run_id: str, *, message: str
    ) -> RunRecord | None:
        updated = self._set_status(
            run_id,
            status=RunStatus.FAILED,
            error={"code": "run_execution_failed", "message": message},
            only_if={RunStatus.RUNNING},
        )
        if updated is not None and updated.status is RunStatus.FAILED:
            log_error(
                "run_failed",
                run_id=run_id,
                session_id=updated.session_id,
                trace_id=updated.trace_id,
                error=message,
            )
            hook_ctx_metadata: dict[str, Any] = {}
            if updated.trace_id:
                hook_ctx_metadata["trace_id"] = updated.trace_id
            hook_ctx = HookContext(
                session_id=updated.session_id,
                turn_id=updated.turn_id,
                metadata=hook_ctx_metadata,
                session_event_publisher=_resolve_session_event_publisher(
                    hook_runner=self._hook_runner,
                    session_id=updated.session_id,
                ),
            )
            await self._dispatch_observe_async(
                "run_error",
                {
                    "session_id": updated.session_id,
                    "run_id": updated.run_id,
                    "error": updated.error,
                },
                hook_ctx,
            )
        return updated

    async def _mark_aborted_async(
        self, run_id: str, *, source: str = "priority_now"
    ) -> RunRecord | None:
        message = (
            "run was aborted by priority=now preemption"
            if source == "priority_now"
            else "run was aborted"
        )
        updated = self._set_status(
            run_id,
            status=RunStatus.CANCELLED,
            stop_reason="aborted",
            error={
                "code": "run_aborted_by_priority_now",
                "message": message,
                "retryable": False,
            },
            only_if={RunStatus.RUNNING},
        )
        if updated is not None and updated.status is RunStatus.CANCELLED:
            log_info(
                "run_aborted",
                run_id=run_id,
                session_id=updated.session_id,
                trace_id=updated.trace_id,
            )
        return updated

    async def _mark_timed_out_async(
        self, run_id: str, *, message: str
    ) -> RunRecord | None:
        updated = self._set_status(
            run_id,
            status=RunStatus.FAILED,
            stop_reason="timeout",
            error={"code": "run_timeout", "message": message},
            only_if={RunStatus.RUNNING},
        )
        if updated is not None and updated.status is RunStatus.FAILED:
            log_error(
                "run_timeout",
                run_id=run_id,
                session_id=updated.session_id,
                trace_id=updated.trace_id,
                error=message,
            )
            hook_ctx_metadata: dict[str, Any] = {}
            if updated.trace_id:
                hook_ctx_metadata["trace_id"] = updated.trace_id
            hook_ctx = HookContext(
                session_id=updated.session_id,
                turn_id=updated.turn_id,
                metadata=hook_ctx_metadata,
                session_event_publisher=_resolve_session_event_publisher(
                    hook_runner=self._hook_runner,
                    session_id=updated.session_id,
                ),
            )
            await self._dispatch_observe_async(
                "run_timeout",
                {
                    "session_id": updated.session_id,
                    "run_id": updated.run_id,
                    "error": updated.error,
                },
                hook_ctx,
            )
        return updated

    async def _dispatch_observe_async(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> None:
        if self._hook_runner is None:
            return
        try:
            diagnostics = await self._hook_runner.dispatch_observe(
                event,
                payload,
                hook_ctx,
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
            hook_ctx.logger.warning(
                "hook observe dispatch failed", event=event, error=str(exc)
            )
            return
        log_hook_diagnostics(hook_ctx, event=event, diagnostics=diagnostics)

    def _persist_run_status_entry(self, record: RunRecord) -> None:
        status_data = _run_status_data(record)
        self._session_manager.append_run_status(
            record.session_id,
            run_id=record.run_id,
            status=record.status.value,
            turn_id=record.turn_id,
            stop_reason=record.stop_reason,
            error=record.error,
            data=status_data,
        )

    def _publish_run_status_event(self, record: RunRecord) -> None:
        status_data = _run_status_data(record)
        if self._event_hub is None:
            return
        payload: dict[str, Any] = {
            "event": "run_status",
            "run_id": record.run_id,
            "status": record.status.value,
            "origin": record.origin.value,
            "source_task_id": record.source_task_id,
            "created_at": record.updated_at,
        }
        if record.turn_id is not None:
            payload["turn_id"] = record.turn_id
        if record.stop_reason is not None:
            payload["stop_reason"] = record.stop_reason
        if record.error is not None:
            payload["error"] = dict(record.error)
        if record.usage is not None:
            payload["usage"] = _serialize_usage(record.usage)
        for key, value in status_data.items():
            payload[key] = value
        self._event_hub.publish(
            event="run_status",
            session_id=record.session_id,
            data=payload,
        )


_TERMINAL_STATUSES = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}

# Canonical string-form terminal run status set derived from the RunStatus enum.
# Exposed via agent.sdk so products can import a single source instead of
# duplicating the {"completed","failed","cancelled"} literal. (refactor-395-M1)
TERMINAL_RUN_STATUSES: frozenset[str] = frozenset(
    s.value for s in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED)
)


def _serialize_usage(usage: TokenUsage | None) -> dict[str, int] | None:
    if usage is None:
        return None
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }


def _extract_run_output_text(turn_result: TurnResult) -> str | None:
    for message in reversed(turn_result.messages):
        if message.role != "assistant":
            continue
        if not isinstance(message.content, str):
            continue
        return message.content
    return None


def _run_status_data(record: RunRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if record.output_text is not None:
        payload["output_text"] = record.output_text
    usage_payload = _serialize_usage(record.usage)
    if usage_payload is not None:
        payload["usage"] = usage_payload
    if record.attempt is not None:
        payload["attempt"] = record.attempt
    if record.next_delay is not None:
        payload["next_delay"] = record.next_delay
    if record.cooldown is not None:
        payload["cooldown"] = record.cooldown
    if record.last_error is not None:
        payload["last_error"] = dict(record.last_error)
    return payload


_SESSION_EVENT_PUBLISHER_FACTORY_STATE_KEY = "session_event_publisher_factory"


def _resolve_session_event_publisher(
    *,
    hook_runner: HookRunner | None,
    session_id: str,
):
    if hook_runner is None:
        return None
    factory = hook_runner.registry.get_extension_state(
        _SESSION_EVENT_PUBLISHER_FACTORY_STATE_KEY
    )
    if not callable(factory):
        return None
    publisher = factory(session_id)
    if not callable(publisher):
        return None
    return publisher
