import time
from pathlib import Path

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.runs.registry import RunStatus, RunsRegistry
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


class _RuntimeStub:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    def run(self, session_id: str, parts, *, stream: bool = True):  # noqa: ANN001, ANN201
        del parts
        del stream
        if self._fail:
            raise RuntimeError("runtime boom")
        return TurnResult(
            session_id=session_id,
            turn_id="turn_async_unit",
            messages=(Message(message_id="msg_async_unit", role="assistant", content="ok"),),
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


def test_runs_registry_transitions_and_persists_status_entries(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "runs-registry.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    registry = RunsRegistry(runtime=_RuntimeStub(), session_manager=manager)

    submitted = registry.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": "hello"}],
    )

    assert submitted.status is RunStatus.QUEUED

    _wait_for(
        lambda: registry.get(submitted.run_id) is not None
        and registry.get(submitted.run_id).status is RunStatus.COMPLETED
    )
    completed = registry.get(submitted.run_id)
    assert completed is not None
    assert completed.turn_id == "turn_async_unit"

    entries = manager.list_entries(session.session_id)
    run_statuses = [
        event.data["status"]
        for event in entries
        if getattr(event.kind, "value", "") == "session.run.status"
    ]
    assert run_statuses == ["queued", "running", "completed"]


def test_runs_registry_marks_failed_when_runtime_raises(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "runs-registry-fail.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    registry = RunsRegistry(runtime=_RuntimeStub(fail=True), session_manager=manager)

    submitted = registry.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": "hello"}],
    )
    _wait_for(
        lambda: registry.get(submitted.run_id) is not None
        and registry.get(submitted.run_id).status is RunStatus.FAILED
    )

    failed = registry.get(submitted.run_id)
    assert failed is not None
    assert failed.error is not None
    assert failed.error["message"] == "runtime boom"
