import time
from threading import Event
from pathlib import Path

from agent.core.errors import ModelError
from agent.core.types import Message, TurnResult
from agent.core.runs.registry import RunStatus, RunsRegistry
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore


class _BlockingRuntime:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None):  # noqa: ANN001, ANN201
        del session_id
        del parts
        del stream
        self.started.set()
        self.release.wait(timeout=1.0)
        return TurnResult(
            session_id="sess_cancel_unit",
            turn_id="turn_cancel_unit",
            messages=(Message(message_id="msg_cancel_unit", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


class _FailureRuntime:
    """Runtime that raises a non-retryable ModelError (simulates loop exhausting retries)."""

    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None):  # noqa: ANN001, ANN201
        del session_id, parts, stream, run_id
        # Retryable errors are exhausted inside loop; what reaches registry is non-retryable.
        raise ModelError("retries exhausted", retryable=False)


def _wait_for(predicate, *, timeout_seconds: float = 1.0) -> None:  # noqa: ANN001
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met before timeout")


def test_cancel_marks_running_run_cancelled_and_is_idempotent(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "run-cancel-unit.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    runtime = _BlockingRuntime()
    registry = RunsRegistry(runtime=runtime, session_manager=manager)

    submitted = registry.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": "cancel me"}],
    )

    _wait_for(lambda: registry.get(submitted.run_id).status is RunStatus.RUNNING)

    first = registry.cancel(submitted.run_id)
    second = registry.cancel(submitted.run_id)

    assert first is not None
    assert second is not None
    assert first.status is RunStatus.CANCELLED
    assert second.status is RunStatus.CANCELLED

    runtime.release.set()
    _wait_for(lambda: registry.get(submitted.run_id).status is RunStatus.CANCELLED)


def test_cancel_unknown_run_returns_none(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "run-cancel-missing.sqlite3")
    manager = SessionManager(store=store)
    registry = RunsRegistry(runtime=_BlockingRuntime(), session_manager=manager)

    assert registry.cancel("run_missing") is None


def test_model_error_from_runtime_marks_run_failed(tmp_path: Path) -> None:
    """ModelError propagating from runtime.run() causes the run to be marked failed.

    After M251, retry is handled inside loop._generate_with_retry(); any ModelError
    that reaches _run_worker means all retries are exhausted and the run is terminal.
    """
    store = SQLiteSessionStore(db_path=tmp_path / "run-model-error-failed.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_FailureRuntime(), session_manager=manager)

    submitted = registry.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": "will fail"}],
    )

    _wait_for(lambda: registry.get(submitted.run_id).status in {RunStatus.FAILED, RunStatus.COMPLETED}, timeout_seconds=2.0)

    final = registry.get(submitted.run_id)
    assert final is not None
    assert final.status is RunStatus.FAILED
