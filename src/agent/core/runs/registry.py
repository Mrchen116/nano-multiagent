from __future__ import annotations

import asyncio
import contextvars
import threading
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Protocol, Sequence

from agent.core.ids import make_run_id
from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.origin import RunOrigin
from agent.core.types import TokenUsage, TurnResult
from agent.core.hooks.context import HookContext
from agent.core.hooks.runner import HookExecution, HookRunner
from agent.core.observability.logger import log_error, log_info
from agent.core.observability.tracing import bind_correlation, current_trace_id, span
from agent.core.session.manager import SessionManager
from agent.core.agent.run_control import RunController


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


class RunsRegistry:
    def __init__(
        self,
        *,
        runtime: RuntimeRunner,
        session_manager: SessionManager,
        event_hub: EventHubLike | None = None,
        hook_runner: HookRunner | None = None,
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

    def shutdown(self) -> None:
        """Stop the dedicated async loop and join its thread."""
        if self._async_loop is not None and self._async_loop.is_running():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        if self._async_thread is not None:
            self._async_thread.join(timeout=5.0)

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
        )
        self._persist_run_status_entry(record)
        with self._lock:
            self._runs[run_id] = record
            self._controllers[run_id] = RunController()
        self._publish_run_status_event(record)
        log_info(
            "run_submitted",
            run_id=run_id,
            session_id=session_id,
            trace_id=resolved_trace_id,
        )

        normalized_parts = [dict(part) for part in parts]
        coro = self._run_worker_async(
            run_id,
            session_id,
            normalized_parts,
            resolved_trace_id,
            workspace_root=workspace_root,
            origin=origin,
        )
        # Capture the caller's Context now (at submit() time) and pass it to the
        # Task so that bind_correlation's ContextVar set/reset both happen inside
        # the same copied Context.  Without this, ensure_future schedules the
        # coroutine in the background thread's default Context, and
        # _context.reset(token) raises "token was created in a different Context"
        # (Issue #3, refactor-387 sdk-fix-r3).
        ctx = contextvars.copy_context()
        self._async_loop.call_soon_threadsafe(
            lambda: self._async_loop.create_task(coro, context=ctx)
        )
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
            hook_ctx.logger.warn(
                "hook observe dispatch failed", event=event, error=str(exc)
            )
            return
        self._log_hook_diagnostics(hook_ctx, event=event, diagnostics=diagnostics)

    @staticmethod
    def _log_hook_diagnostics(
        hook_ctx: HookContext,
        *,
        event: str,
        diagnostics: tuple[HookExecution, ...],
    ) -> None:
        for item in diagnostics:
            if item.status == "ok":
                continue
            hook_ctx.logger.warn(
                "hook execution isolated",
                event=event,
                hook_id=item.hook_id,
                status=item.status,
                duration_ms=item.duration_ms,
                error=item.error,
            )

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


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


_TERMINAL_STATUSES = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}


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
