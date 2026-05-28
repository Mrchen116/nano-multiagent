import asyncio
import time
from threading import Event
from pathlib import Path

from agent.core.errors import ModelError
from agent.core.types import Message, TurnResult
from agent.core.runs.registry import RunStatus, RunsRegistry
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager


class _BlockingRuntime:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None, workspace_root=None, origin=None):  # noqa: ANN001, ANN201
        del session_id
        del parts
        del stream
        del origin
        del workspace_root
        self.started.set()
        self.release.wait(timeout=1.0)
        return TurnResult(
            session_id="sess_cancel_unit",
            turn_id="turn_cancel_unit",
            messages=(Message(message_id="msg_cancel_unit", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


class _AbortableBlockingRuntime:
    """Runtime that checks controller.is_aborted and exits early."""

    def __init__(self) -> None:
        self.started = Event()

    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None, workspace_root=None, origin=None):  # noqa: ANN001, ANN201
        del session_id, parts, stream, run_id, origin, workspace_root
        self.started.set()
        # Poll abort signal with short sleeps
        for _ in range(50):
            if controller is not None and controller.is_aborted:
                return TurnResult(
                    session_id="sess_abort_unit",
                    turn_id="turn_abort_unit",
                    messages=(Message(message_id="msg_abort", role="assistant", content="interrupted"),),
                    completed=False,
                    stop_reason="aborted",
                )
            await asyncio.sleep(0.01)
        return TurnResult(
            session_id="sess_abort_unit",
            turn_id="turn_abort_unit",
            messages=(Message(message_id="msg_timeout", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


class _FailureRuntime:
    """Runtime that raises a non-retryable ModelError (simulates loop exhausting retries)."""

    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None, workspace_root=None, origin=None):  # noqa: ANN001, ANN201
        del session_id, parts, stream, run_id, origin, workspace_root
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
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    runtime = _BlockingRuntime()
    registry = RunsRegistry(runtime=runtime, session_manager=manager)

    try:
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
    finally:
        registry.shutdown()
        runtime.release.set()


def test_cancel_unknown_run_returns_none(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    registry = RunsRegistry(runtime=_BlockingRuntime(), session_manager=manager)

    try:
        assert registry.cancel("run_missing") is None
    finally:
        registry.shutdown()


def test_interrupt_signals_active_run_to_abort(tmp_path: Path) -> None:
    """interrupt() signals the active run's controller to abort."""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    runtime = _AbortableBlockingRuntime()
    registry = RunsRegistry(runtime=runtime, session_manager=manager)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "interrupt me"}],
        )

        _wait_for(lambda: runtime.started.is_set())

        run_id = registry.interrupt(session.session_id)
        assert run_id == submitted.run_id

        # aborted runs are marked CANCELLED (stop_reason="aborted"), not FAILED/COMPLETED
        _wait_for(
            lambda: registry.get(submitted.run_id).status in {RunStatus.FAILED, RunStatus.COMPLETED, RunStatus.CANCELLED},
            timeout_seconds=2.0,
        )

        final = registry.get(submitted.run_id)
        assert final is not None
        assert final.stop_reason == "aborted"
    finally:
        registry.shutdown()


def test_interrupt_no_active_run_returns_none(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    registry = RunsRegistry(runtime=_AbortableBlockingRuntime(), session_manager=manager)

    try:
        assert registry.interrupt("sess_no_active") is None
    finally:
        registry.shutdown()


def test_model_error_from_runtime_marks_run_failed(tmp_path: Path) -> None:
    """ModelError propagating from runtime.run() causes the run to be marked failed.

    After M251, retry is handled inside loop._generate_with_retry(); any ModelError
    that reaches _run_worker means all retries are exhausted and the run is terminal.
    """
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_FailureRuntime(), session_manager=manager)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "will fail"}],
        )

        _wait_for(lambda: registry.get(submitted.run_id).status in {RunStatus.FAILED, RunStatus.COMPLETED}, timeout_seconds=2.0)

        final = registry.get(submitted.run_id)
        assert final is not None
        assert final.status is RunStatus.FAILED
    finally:
        registry.shutdown()
