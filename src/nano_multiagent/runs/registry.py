from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from threading import Event, Lock
import time
from typing import Any, Mapping, Protocol, Sequence

from nano_multiagent.core.errors import ModelError
from nano_multiagent.core.ids import make_run_id
from nano_multiagent.core.types import TokenUsage, TurnResult
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.hooks.runner import HookExecution, HookRunner
from nano_multiagent.hooks.session_events import get_session_event_publisher
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
    usage: TokenUsage | None = None
    attempt: int | None = None
    next_delay: float | None = None
    cooldown: float | None = None
    last_error: Mapping[str, Any] | None = None


class RuntimeRunner(Protocol):
    def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        run_id: str | None = None,
    ):  # noqa: ANN001, ANN201
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
        self._cancel_events: dict[str, Event] = {}

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
            self._cancel_events[run_id] = Event()
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
            cancel_event = self._cancel_events.get(run_id)
        if cancel_event is not None:
            cancel_event.set()
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
        backoff_delays = (0.5, 1.0, 2.0)
        cooldown_every_failures = 5
        cooldown_seconds = 30.0
        backoff_index = 0
        failed_attempts = 0

        with bind_correlation(session_id=session_id, trace_id=trace_id):
            started = self._set_status(
                run_id,
                status=RunStatus.RUNNING,
                only_if={RunStatus.QUEUED},
            )
            if started is None or started.status is not RunStatus.RUNNING:
                return
            log_info("run_started", run_id=run_id)

            while True:
                if self._is_cancelled(run_id):
                    return
                try:
                    result = self._runtime.run(session_id, parts, stream=False, run_id=run_id)
                except TimeoutError as exc:
                    self._mark_timed_out(run_id, message=str(exc))
                    return
                except ModelError as exc:
                    if not exc.retryable:
                        self._mark_failed(run_id, message=str(exc))
                        return

                    failed_attempts += 1
                    next_delay = backoff_delays[backoff_index]
                    backoff_index = (backoff_index + 1) % len(backoff_delays)
                    cooldown = cooldown_seconds if failed_attempts % cooldown_every_failures == 0 else 0.0
                    if cooldown > 0:
                        backoff_index = 0

                    updated = self._set_status(
                        run_id,
                        status=RunStatus.RUNNING,
                        attempt=failed_attempts,
                        next_delay=next_delay,
                        cooldown=cooldown,
                        last_error=_summarize_retry_error(exc),
                        only_if={RunStatus.RUNNING},
                    )
                    if updated is None or updated.status is not RunStatus.RUNNING:
                        return
                    log_info(
                        "run_retry_scheduled",
                        run_id=run_id,
                        attempt=failed_attempts,
                        next_delay=next_delay,
                        cooldown=cooldown,
                    )

                    if not self._sleep_until_retry(run_id=run_id, seconds=next_delay):
                        return
                    if cooldown > 0 and not self._sleep_until_retry(run_id=run_id, seconds=cooldown):
                        return
                    continue
                except Exception as exc:  # noqa: BLE001
                    self._mark_failed(run_id, message=str(exc))
                    return
                self._mark_completed(run_id, turn_result=result)
                return

    def _set_status(
        self,
        run_id: str,
        *,
        status: RunStatus,
        turn_id: str | None = None,
        stop_reason: str | None = None,
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
                error=error,
                usage=usage,
                attempt=attempt,
                next_delay=next_delay,
                cooldown=cooldown,
                last_error=last_error,
            )
            self._runs[run_id] = updated
        self._append_run_status_event(updated)
        return updated

    def _is_cancelled(self, run_id: str) -> bool:
        with self._lock:
            current = self._runs.get(run_id)
            return current is not None and current.status is RunStatus.CANCELLED

    def _sleep_until_retry(self, *, run_id: str, seconds: float) -> bool:
        if seconds <= 0:
            return not self._is_cancelled(run_id)
        with self._lock:
            cancel_event = self._cancel_events.get(run_id)
        if cancel_event is None:
            _sleep(seconds)
            return not self._is_cancelled(run_id)
        cancelled = _wait_with_cancel(cancel_event, seconds)
        if cancelled:
            return False
        return not self._is_cancelled(run_id)

    def _mark_completed(self, run_id: str, *, turn_result: TurnResult) -> RunRecord | None:
        updated = self._set_status(
            run_id,
            status=RunStatus.COMPLETED,
            turn_id=turn_result.turn_id,
            stop_reason=turn_result.stop_reason,
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
                session_event_publisher=_resolve_session_event_publisher(
                    hook_runner=self._hook_runner,
                    session_id=updated.session_id,
                ),
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

    def _mark_timed_out(self, run_id: str, *, message: str) -> RunRecord | None:
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
            self._dispatch_observe(
                "run_timeout",
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
        if record.usage is not None:
            payload["usage"] = _serialize_usage(record.usage)
        for key, value in status_data.items():
            payload[key] = value
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


def _serialize_usage(usage: TokenUsage | None) -> dict[str, int] | None:
    if usage is None:
        return None
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _wait_with_cancel(cancel_event: Event, seconds: float) -> bool:
    return cancel_event.wait(timeout=seconds)


def _summarize_retry_error(error: ModelError) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": error.code,
        "message": _truncate_error_message(error.message),
        "retryable": error.retryable,
    }
    if error.details:
        payload["details"] = dict(error.details)
    return payload


def _truncate_error_message(message: str, *, max_chars: int = 240) -> str:
    if len(message) <= max_chars:
        return message
    return f"{message[:max_chars]}..."


def _run_status_data(record: RunRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {}
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


def _resolve_session_event_publisher(
    *,
    hook_runner: HookRunner | None,
    session_id: str,
):
    if hook_runner is None:
        return None
    return get_session_event_publisher(
        registry=hook_runner.registry,
        session_id=session_id,
    )
