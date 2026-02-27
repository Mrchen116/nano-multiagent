from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Any, Mapping, Protocol, Sequence

from nano_multiagent.core.ids import make_run_id
from nano_multiagent.core.types import TurnResult
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
        max_workers: int = 4,
    ) -> None:
        self._runtime = runtime
        self._session_manager = session_manager
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="nano-runs")
        self._lock = Lock()
        self._runs: dict[str, RunRecord] = {}

    def submit(
        self,
        *,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
    ) -> RunRecord:
        if self._session_manager.get_session(session_id) is None:
            raise ValueError(f"session does not exist: {session_id}")
        if not parts:
            raise ValueError("empty input parts are not allowed")

        run_id = make_run_id()
        now = _utc_now_iso()
        record = RunRecord(
            run_id=run_id,
            session_id=session_id,
            status=RunStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._runs[run_id] = record
        self._append_run_status_event(record)

        normalized_parts = [dict(part) for part in parts]
        self._executor.submit(self._run_worker, run_id, session_id, normalized_parts)
        return record

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return None
            return replace(record)

    def _run_worker(
        self,
        run_id: str,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
    ) -> None:
        started = self._transition(run_id, status=RunStatus.RUNNING)
        if started is None:
            return

        try:
            result = self._runtime.run(session_id, parts, stream=False)
        except Exception as exc:  # noqa: BLE001
            self._mark_failed(run_id, message=str(exc))
            return
        self._mark_completed(run_id, turn_result=result)

    def _transition(
        self,
        run_id: str,
        *,
        status: RunStatus,
        turn_id: str | None = None,
        stop_reason: str | None = None,
        error: Mapping[str, Any] | None = None,
    ) -> RunRecord | None:
        with self._lock:
            current = self._runs.get(run_id)
            if current is None:
                return None
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
        return self._transition(
            run_id,
            status=RunStatus.COMPLETED,
            turn_id=turn_result.turn_id,
            stop_reason=turn_result.stop_reason,
            error=None,
        )

    def _mark_failed(self, run_id: str, *, message: str) -> RunRecord | None:
        return self._transition(
            run_id,
            status=RunStatus.FAILED,
            error={"code": "run_execution_failed", "message": message},
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


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
