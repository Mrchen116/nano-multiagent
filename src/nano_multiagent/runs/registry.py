from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Any, Mapping, Protocol, Sequence

from nano_multiagent.core.ids import make_run_id
from nano_multiagent.core.types import TurnResult
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.hooks.runner import HookExecution, HookRunner
from nano_multiagent.observability.logger import log_error, log_info
from nano_multiagent.observability.tracing import bind_correlation, current_trace_id
from nano_multiagent.server.sse import EventStreamHub
from nano_multiagent.session.manager import SessionManager


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
    error: Mapping[str, Any] | None = None


class RuntimeRunner(Protocol):
    def run(self, session_id: str, parts, *, stream: bool = True):  # noqa: ANN001, ANN201
        ...


class RunsRegistry:
    def __init__(
        self,
        *,
        runtime: RuntimeRunner,
        session_manager: SessionManager,
        event_hub: EventStreamHub | None = None,
        hook_runner: HookRunner | None = None,
        max_workers: int = 4,
    ) -> None:
        self._runtime = runtime
        self._session_manager = session_manager
        self._event_hub = event_hub
        self._hook_runner = hook_runner
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="nano-runs")
        self._lock = Lock()
        self._runs: dict[str, RunRecord] = {}

    def submit(
        self,
        *,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
        trace_id: str | None = None,
    ) -> RunRecord:
        if self._session_manager.get_session(session_id) is None:
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
        )
        with self._lock:
            self._runs[run_id] = record
        self._append_run_status_event(record)
        log_info(
            "run_submitted",
            run_id=run_id,
            session_id=session_id,
            trace_id=resolved_trace_id,
        )

        normalized_parts = [dict(part) for part in parts]
        self._executor.submit(self._run_worker, run_id, session_id, normalized_parts, resolved_trace_id)
        return record

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return None
            return replace(record)

    def cancel(self, run_id: str) -> RunRecord | None:
        with self._lock:
            current = self._runs.get(run_id)
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

    def _run_worker(
        self,
        run_id: str,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
        trace_id: str | None,
    ) -> None:
        with bind_correlation(session_id=session_id, trace_id=trace_id):
            started = self._set_status(
                run_id,
                status=RunStatus.RUNNING,
                only_if={RunStatus.QUEUED},
            )
            if started is None or started.status is not RunStatus.RUNNING:
                return
            log_info("run_started", run_id=run_id)

            try:
                result = self._runtime.run(session_id, parts, stream=False)
            except Exception as exc:  # noqa: BLE001
                self._mark_failed(run_id, message=str(exc))
                return
            self._mark_completed(run_id, turn_result=result)

    def _set_status(
        self,
        run_id: str,
        *,
        status: RunStatus,
        turn_id: str | None = None,
        stop_reason: str | None = None,
        error: Mapping[str, Any] | None = None,
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
                error=error,
            )
            self._runs[run_id] = updated
        self._append_run_status_event(updated)
        return updated

    def _mark_completed(self, run_id: str, *, turn_result: TurnResult) -> RunRecord | None:
        updated = self._set_status(
            run_id,
            status=RunStatus.COMPLETED,
            turn_id=turn_result.turn_id,
            stop_reason=turn_result.stop_reason,
            error=None,
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
            self._emit_turn_events(record=updated, turn_result=turn_result)
        return updated

    def _mark_failed(self, run_id: str, *, message: str) -> RunRecord | None:
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
            )
            self._dispatch_observe(
                "run_error",
                {
                    "session_id": updated.session_id,
                    "run_id": updated.run_id,
                    "error": updated.error,
                },
                hook_ctx,
            )
        return updated

    def _dispatch_observe(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> None:
        if self._hook_runner is None:
            return
        try:
            diagnostics = asyncio.run(
                self._hook_runner.dispatch_observe(
                    event,
                    payload,
                    hook_ctx,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
            hook_ctx.logger.warn("hook observe dispatch failed", event=event, error=str(exc))
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

    def _append_run_status_event(self, record: RunRecord) -> None:
        self._session_manager.append_run_status(
            record.session_id,
            run_id=record.run_id,
            status=record.status.value,
            turn_id=record.turn_id,
            stop_reason=record.stop_reason,
            error=record.error,
        )
        if self._event_hub is None:
            return
        payload: dict[str, Any] = {
            "event": "run_status",
            "run_id": record.run_id,
            "status": record.status.value,
            "created_at": record.updated_at,
        }
        if record.turn_id is not None:
            payload["turn_id"] = record.turn_id
        if record.stop_reason is not None:
            payload["stop_reason"] = record.stop_reason
        if record.error is not None:
            payload["error"] = dict(record.error)
        self._event_hub.publish(
            event="run_status",
            session_id=record.session_id,
            data=payload,
        )

    def _emit_turn_events(self, *, record: RunRecord, turn_result: TurnResult) -> None:
        if self._event_hub is None:
            return

        for tool_call in turn_result.tool_calls:
            self._event_hub.publish(
                event="tool_start",
                session_id=record.session_id,
                data={
                    "event": "tool_start",
                    "run_id": record.run_id,
                    "turn_id": turn_result.turn_id,
                    "call_id": tool_call.call_id,
                    "name": tool_call.name,
                    "arguments": dict(tool_call.arguments),
                },
            )
        for tool_result in turn_result.tool_results:
            self._event_hub.publish(
                event="tool_end",
                session_id=record.session_id,
                data={
                    "event": "tool_end",
                    "run_id": record.run_id,
                    "turn_id": turn_result.turn_id,
                    "call_id": tool_result.call_id,
                    "name": tool_result.name,
                    "output": tool_result.output,
                    "error": tool_result.error,
                },
            )
        for message in turn_result.messages:
            if message.role != "assistant":
                continue
            self._event_hub.publish(
                event="text_delta",
                session_id=record.session_id,
                data={
                    "event": "text_delta",
                    "run_id": record.run_id,
                    "turn_id": turn_result.turn_id,
                    "message_id": message.message_id,
                    "delta": message.content,
                },
            )
        self._event_hub.publish(
            event="turn_end",
            session_id=record.session_id,
            data={
                "event": "turn_end",
                "run_id": record.run_id,
                "turn_id": turn_result.turn_id,
                "completed": turn_result.completed,
                "stop_reason": turn_result.stop_reason,
            },
        )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


_TERMINAL_STATUSES = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
