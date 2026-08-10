from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from threading import Lock
from collections.abc import Awaitable, Callable
from typing import Any, Mapping, Protocol, Sequence

from agent.core.ids import make_run_id
from agent.core.errors import CompactionError
from agent.core.utils.time import utc_now_iso as _utc_now_iso
from agent.core.llm.interfaces import LLMMessage
from agent.core.background_tasks.notifications import BackgroundReturnInfo
from agent.core.runs.origin import RunOrigin
from agent.core.types import TokenUsage, TurnResult
from agent.core.hooks.context import HookContext
from agent.core.hooks.runner import HookRunner, log_hook_diagnostics
from agent.core.observability.logger import log_error, log_info
from agent.core.observability.tracing import current_trace_id
from agent.core.runs.executor import KernelExecutor, TargetCompletion, TargetToken
from agent.core.session.directory import SessionDirectory
from agent.core.session.types import SessionRef, TurnRequest
from agent.core.agent.run_control import PendingMessage, RunController
from agent.core.workspace import WorkspaceExecutionScope


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
    source_background_returns: tuple[BackgroundReturnInfo, ...] = ()
    # bugfix-429: the model this run executes with, supplied by the product layer
    # per submit (agent.default_model). submit is async-queued (background worker)
    # and the kernel self-continues stranded runs, so the model must live on the
    # record — a sync pass-through would be lost across both hops. Kernel continuation
    # reuses *this* run's model (in-progress run finishes on its original model).
    model: str | None = None
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


class EventHubLike(Protocol):
    def publish(
        self, *, event: str, session_id: str, data: dict[str, Any]
    ) -> object: ...

    def current_sequence(self) -> int: ...


class ForegroundStopper(Protocol):
    """Port for reaping a session's in-flight foreground tool subprocess tree.

    Injected by the kernel (wired to ForegroundExecutionRegistry.stop_for_session)
    so the core RunsRegistry can kill a run-blocking foreground tool on interrupt /
    cancel without importing the platform layer (bugfix-417-M5, #114 / M7 decision 12).
    Returns True when an in-flight foreground tool existed and was stopped.
    """

    def __call__(self, session_id: str) -> bool: ...


class RunsRegistry:
    def __init__(
        self,
        *,
        directory: SessionDirectory,
        executor: KernelExecutor,
        event_hub: EventHubLike | None = None,
        hook_runner: HookRunner | None = None,
        foreground_stopper: "ForegroundStopper | None" = None,
        drain_timeout_seconds: float = 30.0,
    ) -> None:
        self._directory = directory
        self._executor = executor
        self._event_hub = event_hub
        self._hook_runner = hook_runner
        self._execution_scope_resolver: (
            Callable[[Path], WorkspaceExecutionScope] | None
        ) = None
        # Injected port (core stays platform-free): kills the in-flight foreground
        # tool's subprocess tree for a session and reports whether one existed.
        # Wired by the kernel to ForegroundExecutionRegistry.stop_for_session
        # (bugfix-417-M5, #114 / M7 decision 12). None → no foreground reap (degrades
        # to the pre-existing cooperative-abort / force-cancel behaviour).
        self._foreground_stopper = foreground_stopper
        self._lock = Lock()
        self._runs: dict[str, RunRecord] = {}
        self._controllers: dict[str, RunController] = {}
        # session_id → run_id for the currently-executing run (RUNNING state only).
        self._active_run_by_session: dict[str, str] = {}
        # bugfix-426 决策3 (held-pending): when a user /stop ends a run, messages that
        # were steered into it but never consumed are NOT auto-continued (that would
        # contradict the explicit stop) and NOT discarded (that would lose the user's
        # later intent); they are parked here per session and prepended to the NEXT
        # submit() for that session. In-memory, lost on restart (same as pending).
        self._held_pending: dict[str, list[PendingMessage]] = {}
        self._target_tokens: dict[str, TargetToken] = {}
        self._cleanup_acks: set[str] = set()
        # Lifecycle state: OPEN → DRAINING → CLOSED (see _RegistryState).
        self._state: _RegistryState = _RegistryState.OPEN
        self._drain_timeout_seconds = drain_timeout_seconds

    def begin_shutdown(self) -> bool:
        """Stop semantic run admission before executor draining begins."""

        with self._lock:
            if self._state is _RegistryState.CLOSED:
                return False
            self._state = _RegistryState.DRAINING
            return True

    def shutdown(
        self,
        *,
        grace_timeout_seconds: float | None = None,
        finalize: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Close run admission, drain carriers, then run owner-loop finalization."""

        self.begin_shutdown()
        self._executor.shutdown(timeout=grace_timeout_seconds, finalize=finalize)
        with self._lock:
            self._state = _RegistryState.CLOSED

    def submit(
        self,
        *,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
        origin: RunOrigin = RunOrigin.USER,
        source_task_id: str | None = None,
        source_background_returns: Sequence[BackgroundReturnInfo] = (),
        trace_id: str | None = None,
        workspace_root: Path | None = None,
        flush_held: bool = True,
        model: str | None = None,
    ) -> RunRecord:
        """Prepare semantic state, bind an executor token, then publish the run."""

        if workspace_root is None:
            raise ValueError("workspace_root is required to submit a session")
        if not parts:
            raise ValueError("empty input parts are not allowed")
        with self._lock:
            if self._state is not _RegistryState.OPEN:
                raise RegistryClosedError(
                    "registry is shutting down; no new runs will be accepted"
                )
            held = self._held_pending.pop(session_id, None) if flush_held else None
        normalized_parts: list[Mapping[str, Any]] = []
        normalized_background_returns: list[BackgroundReturnInfo] = []
        if held:
            for pending in held:
                normalized_parts.extend(_input_parts_from_message(pending.message))
                if pending.background_return is not None:
                    normalized_background_returns.append(pending.background_return)
        normalized_parts.extend(dict(part) for part in parts)
        normalized_background_returns.extend(source_background_returns)

        ref = SessionRef(session_id=session_id, workspace_root=workspace_root)
        if self._directory.get(ref) is None:
            if held:
                with self._lock:
                    self._held_pending.setdefault(session_id, [])[:0] = held
            raise ValueError(f"session does not exist: {session_id}")
        session = self._directory.open(ref)
        run_id = make_run_id()
        now = _utc_now_iso()
        resolved_trace_id = trace_id or current_trace_id()
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
            source_background_returns=tuple(normalized_background_returns),
            workspace_root=ref.workspace_root,
            start_sequence=start_sequence,
            model=model,
        )
        controller = RunController()
        sink = _RegistryCompletionSink(
            registry=self,
            record=record,
            controller=controller,
        )
        try:
            self._executor.start_top_level(
                run_id,
                session,
                TurnRequest(
                    parts=tuple(normalized_parts),
                    run_id=run_id,
                    controller=controller,
                    origin=origin,
                    model=model,
                    source_background_returns=tuple(
                        item.to_dict() for item in normalized_background_returns
                    ),
                ),
                sink,
            )
        except Exception:
            if held:
                with self._lock:
                    self._held_pending.setdefault(session_id, [])[:0] = held
            raise
        return record

    def set_foreground_stopper(self, stopper: "ForegroundStopper | None") -> None:
        """Inject the foreground-tool subprocess reaper after construction.

        The platform-owned foreground registry is composed after this core object,
        so the narrow stopper port remains late-bound without exposing executor state.
        """
        self._foreground_stopper = stopper

    def set_execution_scope_resolver(
        self, resolver: Callable[[Path], WorkspaceExecutionScope] | None
    ) -> None:
        """Install the workspace scope resolver used for terminal run hooks."""

        self._execution_scope_resolver = resolver

    def get_active_run_id(self, session_id: str) -> str | None:
        """Return the run_id of the currently-executing run for a session, or None."""
        with self._lock:
            return self._active_run_by_session.get(session_id)

    def interrupt(self, session_id: str) -> str | None:
        """Signal force interrupt for the active run of a session.

        Cooperatively aborts the active run (controller flag). When the run is
        parked inside a blocking foreground tool (long shell command), the
        cooperative flag alone cannot unwind the carrier Task — it is stuck on
        the tool's to_thread that never returns until the subprocess is killed.
        So, when an in-flight foreground tool exists, this additionally (a) kills
        its subprocess tree via the injected foreground stopper and (b)
        force-cancels the carrier Task so the parked await unwinds, the
        per-session lock is released, and the runtime's CancelledError finally
        recovers the orphaned tool_call as "interrupted" (bugfix-417-M5, #114).
        Every accepted user interrupt force-cancels its carrier after foreground
        reaping. This prevents provider or hook awaits from resuming after /stop
        returned and releases the session lock without a grace-window race.

        Returns the run_id if an active run was found and signalled, None otherwise.
        """
        with self._lock:
            run_id = self._active_run_by_session.get(session_id)
            controller = self._controllers.get(run_id) if run_id else None
        if controller is None:
            return None
        # interrupt() is the user-initiated stop path (/stop, CLI Ctrl-C), so mark
        # the abort user-initiated — the runtime then recovers any orphaned
        # tool_call with the CC-identical user-attribution content (bugfix-417-M5).
        controller.abort(user_initiated=True)
        # bugfix-426 决策3 (/stop held-pending, sync): park any unconsumed steered
        # messages to the session held buffer NOW, synchronously, before returning.
        # The gateway /stop handler synchronously submit()s a "/stop 命令" turn right
        # after this call; if held population waited for the async terminal chokepoint
        # (_settle_terminal_pending, runs when the carrier Task unwinds on the bg
        # loop) it would be EMPTY at that submit and the user's steered message lost.
        # Draining here empties the controller, so the later _settle_terminal_pending
        # drains nothing → natural no-op, no double-move (and /stop never continues).
        stranded = controller.drain_pending()
        if stranded:
            with self._lock:
                self._held_pending.setdefault(session_id, []).extend(stranded)
        log_info("run_interrupted", run_id=run_id, session_id=session_id)
        # Reap an in-flight foreground tool's subprocess tree; if one existed, the
        # cooperative abort cannot unwind the parked carrier Task, so force-cancel
        # it (its `async with lock` then exits via CancelledError, releasing the
        # session lock; the runtime finally closes the orphan as "interrupted").
        if self._foreground_stopper is not None:
            self._foreground_stopper(session_id)
        # User-visible interrupt is a synchronous semantic terminal. Linearize
        # CANCELLED before returning so a provider completing inside the executor's
        # cooperative grace cannot publish COMPLETED over an accepted /stop.
        controller.cancel()
        self._set_status(
            run_id,
            status=RunStatus.CANCELLED,
            stop_reason="cancelled",
            only_if={RunStatus.QUEUED, RunStatus.RUNNING},
        )
        # /stop is a hard user boundary. Force-cancel every carrier after reaping
        # any foreground subprocess so a provider, permission wait, or observe hook
        # cannot resume and publish output after interrupt() has returned.
        self._request_target_cancel(run_id, force=True)
        return run_id

    def inject_pending_message(
        self,
        session_id: str,
        message: LLMMessage,
        origin: RunOrigin = RunOrigin.USER,
        *,
        expected_run_id: str | None = None,
        background_return: BackgroundReturnInfo | None = None,
    ) -> bool:
        """Enqueue a message for round-boundary injection into the active run.

        Args:
            session_id: Session whose active run to inject into.
            message: Message to inject before the active run's next LLM call.
            origin: Source that produced this message. Carried on the pending
                queue so a stranded continuation re-run keeps the right origin
                (user mid-run steer → USER, not BACKGROUND_TASK; bugfix-426 决策3).
            expected_run_id: Optional caller-owned active marker. When supplied,
                injection is rejected unless that exact run is still active.

        Returns:
            True if the message was enqueued, False if no active run exists, the
            run is already being interrupted, or the run already committed its
            terminal (bugfix-426-M4 决策5: the loop decided to finish in the window
            between its last drain and the break — the steer lost the race and the
            caller must route it to a new run, not lose it).
        """
        return (
            self.try_inject_pending_message(
                session_id,
                message,
                origin,
                expected_run_id=expected_run_id,
                background_return=background_return,
            )
            is not None
        )

    def try_inject_pending_message(
        self,
        session_id: str,
        message: LLMMessage,
        origin: RunOrigin = RunOrigin.USER,
        *,
        expected_run_id: str | None = None,
        background_return: BackgroundReturnInfo | None = None,
    ) -> str | None:
        """Atomically compare, inject, and return the accepted active run identity.

        Args:
            session_id: Session whose active run may receive the message.
            message: Message to inject before the run's next LLM call.
            origin: Source preserved on the pending message.
            expected_run_id: Optional caller-owned active marker. A mismatch
                rejects the operation without injecting into a replacement run.

        Returns:
            The exact run id whose controller accepted the message, or ``None``
            when no matching active run can accept it.

        Notes:
            The registry lock remains held through the controller's non-blocking
            enqueue so active-run replacement cannot interleave between comparison
            and admission.
        """

        with self._lock:
            run_id = self._active_run_by_session.get(session_id)
            if expected_run_id is not None and run_id != expected_run_id:
                return None
            controller = self._controllers.get(run_id) if run_id else None
            if controller is None:
                return None
            # Controller admission shares its terminal lock with the loop's terminal
            # commit. Keeping both locks through enqueue makes active identity and
            # terminal acceptance one linearizable decision.
            if not controller.enqueue_message(message, origin, background_return):
                return None
            return run_id

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
        updated = self._set_status(
            run_id,
            status=RunStatus.CANCELLED,
            stop_reason="cancelled",
            only_if={RunStatus.QUEUED, RunStatus.RUNNING},
        )
        # bugfix-417-M5: reap an in-flight foreground tool's subprocess tree for
        # this run's session so cancel leaves no orphan (M1 force-cancels the
        # carrier Task to release the lock, but the killed subprocess must also be
        # reaped — otherwise the to_thread's killpg never fires; #114).
        if self._foreground_stopper is not None:
            self._foreground_stopper(current.session_id)
        # bugfix-417-M1: cooperative cancel (controller flag) cannot reach a run
        # parked inside an await it never returns from (tool execution / LLM wait
        # / permission decision). The run holds the per-session lock until its
        # carrier Task unwinds, so a parked run would otherwise wedge the session
        # forever (#110). Force-cancel the carrier Task on the registry's own loop
        # so `async with lock` exits via CancelledError and releases the lock; the
        # runtime's CancelledError path recovers orphaned tool_calls under shield.
        self._request_target_cancel(run_id)
        return updated

    def _request_target_cancel(self, run_id: str, *, force: bool = False) -> None:
        with self._lock:
            token = self._target_tokens.get(run_id)
        if token is not None:
            self._executor.request_cancel(token, force=force)

    def _bind_target(
        self,
        *,
        record: RunRecord,
        controller: RunController,
        token: TargetToken,
    ) -> None:
        with self._lock:
            if self._state is not _RegistryState.OPEN:
                raise RegistryClosedError(
                    "registry is shutting down; no new runs will be accepted"
                )
            self._runs[record.run_id] = record
            self._controllers[record.run_id] = controller
            self._target_tokens[record.run_id] = token
            self._persist_run_status_entry(record)
        self._publish_run_status_event(record)
        log_info(
            "run_submitted",
            run_id=record.run_id,
            session_id=record.session_id,
            trace_id=record.trace_id,
        )

    def _target_started(self, run_id: str) -> None:
        started = self._set_status(
            run_id,
            status=RunStatus.RUNNING,
            only_if={RunStatus.QUEUED},
        )
        if started is None or started.status is not RunStatus.RUNNING:
            return
        with self._lock:
            controller = self._controllers.get(run_id)
            if controller is not None and not controller.is_cancelled:
                self._active_run_by_session[started.session_id] = run_id
        log_info("run_started", run_id=run_id)

    def _target_completed(self, run_id: str, completion: TargetCompletion) -> None:
        with self._lock:
            record = self._runs.get(run_id)
            controller = self._controllers.get(run_id)
            if (
                record is not None
                and self._active_run_by_session.get(record.session_id) == run_id
            ):
                self._active_run_by_session.pop(record.session_id, None)
            self._target_tokens.pop(run_id, None)
            self._cleanup_acks.add(run_id)
        if record is None:
            return

        async def _finish() -> None:
            try:
                current = self.get(run_id)
                if current is None:
                    return
                if current.status not in _TERMINAL_STATUSES:
                    if completion.cancelled:
                        await self._mark_aborted_async(run_id, source="cancel")
                    elif isinstance(completion.error, TimeoutError):
                        await self._mark_timed_out_async(
                            run_id, message=str(completion.error)
                        )
                    elif completion.error is not None:
                        await self._mark_failed_async(
                            run_id,
                            error=(
                                completion.error.to_dict()
                                if isinstance(completion.error, CompactionError)
                                else {
                                    "code": "run_execution_failed",
                                    "message": str(completion.error),
                                }
                            ),
                        )
                    elif completion.result is not None:
                        if completion.result.stop_reason == "aborted":
                            await self._mark_aborted_async(run_id)
                        else:
                            self._mark_completed(run_id, turn_result=completion.result)
            finally:
                self._settle_terminal_pending(
                    controller,
                    session_id=record.session_id,
                    workspace_root=record.workspace_root,
                    model=record.model,
                )

        asyncio.get_running_loop().create_task(_finish())

    def _settle_terminal_pending(
        self,
        controller: RunController | None,
        *,
        session_id: str,
        workspace_root: Path | None,
        model: str | None = None,
    ) -> None:
        """Settle messages injected into a now-terminal run (bugfix-426 决策3).

        Single terminal chokepoint. A message steered into an active run via
        ``inject_pending_message`` that the loop never consumed at a round boundary
        would otherwise be lost when the run ends — violating incident「消息不丢失」.
        Two outcomes by how the run ended:

        - **User /stop** (``controller.is_user_interrupt``): the user explicitly
          stopped, so neither auto-continue (contradicts /stop, and bugfix-417's
          /stop ack already told the user it stopped) nor discard (loses the user's
          later intent). Park the drained messages to the session-level held buffer;
          the next ``submit()`` for this session prepends them.
        - **Non-user terminal** (watchdog idle-reap / crash / timeout / completion):
          re-run as a continuation carrying each message's own injection origin
          (user steer → USER), grouped into contiguous same-origin batches to
          preserve FIFO order. No-op when the registry is shutting down (submit
          would raise) so a force-cancel during shutdown unwinds cleanly.

        ``model`` (bugfix-429) is the terminating run's product-supplied model; a
        continuation re-run carries it so it executes on the same model, not the
        kernel default.
        """
        if controller is None:
            return
        stranded = controller.drain_pending()
        if not stranded:
            return
        # is_user_interrupt gates the held-pending vs auto-continuation split: a user
        # /stop parks the steer for the next submit (neither dropped nor auto-continued,
        # matching bugfix-417's "已停止" ack); any non-user terminal (watchdog/crash/
        # timeout) auto-continues it. interrupt() also drains synchronously, so for a
        # /stop this drain is usually already empty — this branch is the belt-and-braces
        # path for a steer that slipped in between interrupt() and this chokepoint.
        if controller.is_user_interrupt:
            with self._lock:
                self._held_pending.setdefault(session_id, []).extend(stranded)
            return
        with self._lock:
            if self._state is not _RegistryState.OPEN:
                return
        for origin_batch, pending_batch in _group_pending_by_origin(stranded):
            self.submit(
                session_id=session_id,
                parts=[
                    part
                    for pending in pending_batch
                    for part in _input_parts_from_message(pending.message)
                ],
                origin=origin_batch,
                source_background_returns=tuple(
                    pending.background_return
                    for pending in pending_batch
                    if pending.background_return is not None
                ),
                workspace_root=workspace_root,
                model=model,
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
        self, run_id: str, *, error: Mapping[str, Any]
    ) -> RunRecord | None:
        updated = self._set_status(
            run_id,
            status=RunStatus.FAILED,
            error=error,
            only_if={RunStatus.RUNNING},
        )
        if updated is not None and updated.status is RunStatus.FAILED:
            log_error(
                "run_failed",
                run_id=run_id,
                session_id=updated.session_id,
                trace_id=updated.trace_id,
                error=str(error.get("message", "run failed")),
            )
            hook_runner, hook_ctx = self._hook_context_for(updated)
            await self._dispatch_observe_async(
                "run_error",
                {
                    "session_id": updated.session_id,
                    "run_id": updated.run_id,
                    "error": updated.error,
                },
                hook_ctx,
                hook_runner=hook_runner,
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
            hook_runner, hook_ctx = self._hook_context_for(updated)
            await self._dispatch_observe_async(
                "run_timeout",
                {
                    "session_id": updated.session_id,
                    "run_id": updated.run_id,
                    "error": updated.error,
                },
                hook_ctx,
                hook_runner=hook_runner,
            )
        return updated

    async def _dispatch_observe_async(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
        *,
        hook_runner: HookRunner | None = None,
    ) -> None:
        effective_hook_runner = hook_runner or self._hook_runner
        if effective_hook_runner is None:
            return
        try:
            diagnostics = await effective_hook_runner.dispatch_observe(
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

    def _hook_context_for(
        self, record: RunRecord
    ) -> tuple[HookRunner | None, HookContext]:
        """Build terminal-hook context from the run's selected workspace scope."""

        scope = (
            self._execution_scope_resolver(record.workspace_root)
            if self._execution_scope_resolver is not None
            and record.workspace_root is not None
            else None
        )
        hook_runner = scope.hook_runner if scope is not None else self._hook_runner
        metadata: Mapping[str, Any] = (
            {
                "trace_id": record.trace_id,
            }
            if record.trace_id
            else {}
        )
        if scope is not None:
            metadata = scope.metadata(metadata)
        return hook_runner, HookContext(
            session_id=record.session_id,
            turn_id=record.turn_id,
            repo_root=(
                scope.layout.workspace_root
                if scope is not None
                else record.workspace_root
            ),
            metadata=metadata,
            session_event_publisher=_resolve_session_event_publisher(
                hook_runner=hook_runner,
                session_id=record.session_id,
            ),
        )

    def _persist_run_status_entry(self, record: RunRecord) -> None:
        # JSONL architecture keeps run status in the event hub; this remains a
        # named hook so the semantic writer has one stable call site.
        del record

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
        if record.source_background_returns:
            payload["background_returns"] = [
                item.to_dict() for item in record.source_background_returns
            ]
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


@dataclass(slots=True)
class _RegistryCompletionSink:
    registry: RunsRegistry
    record: RunRecord
    controller: RunController

    def bind_target(self, token: TargetToken) -> None:
        self.registry._bind_target(
            record=self.record,
            controller=self.controller,
            token=token,
        )

    def started(self, token: TargetToken) -> None:
        if token.owner_id != self.record.run_id:
            raise RuntimeError("executor bound a token to the wrong run")
        self.registry._target_started(self.record.run_id)

    def complete(self, completion: TargetCompletion) -> None:
        self.registry._target_completed(self.record.run_id, completion)


_TERMINAL_STATUSES = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}

# Canonical string-form terminal run status set derived from the RunStatus enum.
# Exposed via agent.sdk so products can import a single source instead of
# duplicating the {"completed","failed","cancelled"} literal. (refactor-395-M1)
TERMINAL_RUN_STATUSES: frozenset[str] = frozenset(
    s.value for s in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED)
)


def _group_pending_by_origin(
    pending: list[PendingMessage],
) -> list[tuple[RunOrigin, list[PendingMessage]]]:
    """Group stranded pending messages into contiguous same-origin batches.

    Preserves FIFO order: each batch is a maximal run of consecutive items sharing
    one origin, so a continuation run is submitted per batch with that origin.
    """
    batches: list[tuple[RunOrigin, list[PendingMessage]]] = []
    for item in pending:
        if batches and batches[-1][0] == item.origin:
            batches[-1][1].append(item)
        else:
            batches.append((item.origin, [item]))
    return batches


def _input_parts_from_message(message: LLMMessage) -> list[Mapping[str, Any]]:
    """Recover canonical submit parts from a pending provider-neutral message."""

    if isinstance(message.content, str):
        return [{"type": "text", "text": message.content}]
    return [dict(part) for part in message.content]


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
