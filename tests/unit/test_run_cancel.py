import time
from threading import Event
from pathlib import Path

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.runs.registry import RunStatus, RunsRegistry
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


class _BlockingRuntime:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def run(self, session_id: str, parts, *, stream: bool = True):  # noqa: ANN001, ANN201
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
    session = manager.create_session()
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
