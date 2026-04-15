import time
from pathlib import Path

from agent.core.errors import ModelError
from agent.core.types import Message, TokenUsage, TurnResult
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.runs.registry import RunStatus, RunsRegistry
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore


class _RuntimeStub:
    def __init__(self, *, fail: bool = False, timeout: bool = False) -> None:
        self._fail = fail
        self._timeout = timeout

    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None):  # noqa: ANN001, ANN201
        del parts
        del stream
        if self._timeout:
            raise TimeoutError("runtime timed out")
        if self._fail:
            raise RuntimeError("runtime boom")
        return TurnResult(
            session_id=session_id,
            turn_id="turn_async_unit",
            messages=(Message(message_id="msg_async_unit", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


class _RuntimeWithUsageStub:
    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None):  # noqa: ANN001, ANN201
        del parts
        del stream
        return TurnResult(
            session_id=session_id,
            turn_id="turn_async_usage",
            messages=(Message(message_id="msg_async_usage", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
            usage=TokenUsage(prompt_tokens=200, completion_tokens=20, total_tokens=220),
        )


class _RetryableModelErrorRuntime:
    """Runtime that raises a retryable ModelError, simulating loop-exhausted errors reaching registry."""

    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None):  # noqa: ANN001, ANN201
        del session_id, parts, stream, run_id
        # After M251 retry lives in loop; retryable errors that reach registry are terminal.
        raise ModelError("transient upstream blip", retryable=True)


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
    assert completed.output_text == "ok"

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


def test_runs_registry_persists_completed_run_usage(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "runs-registry-usage.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    registry = RunsRegistry(runtime=_RuntimeWithUsageStub(), session_manager=manager)

    submitted = registry.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": "hello"}],
    )
    _wait_for(
        lambda: registry.get(submitted.run_id) is not None
        and registry.get(submitted.run_id).status is RunStatus.COMPLETED
    )

    completed = registry.get(submitted.run_id)
    assert completed is not None
    assert completed.usage is not None
    assert completed.usage.total_tokens == 220

    entries = manager.list_entries(session.session_id)
    completed_entries = [
        event
        for event in entries
        if getattr(event.kind, "value", "") == "session.run.status" and event.data.get("status") == "completed"
    ]
    assert completed_entries
    assert completed_entries[-1].data.get("output_text") == "ok"
    assert completed_entries[-1].data.get("usage") == {
        "prompt_tokens": 200,
        "completion_tokens": 20,
        "total_tokens": 220,
    }


def test_runs_registry_dispatches_run_error_observe_hook_when_runtime_raises(tmp_path: Path) -> None:
    observed_events: list[dict[str, object]] = []
    hooks = HookRegistry()

    async def on_run_error(event, ctx):
        del ctx
        observed_events.append(dict(event))

    hooks.on("run_error", on_run_error)

    store = SQLiteSessionStore(db_path=tmp_path / "runs-registry-run-error-hook.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    registry = RunsRegistry(
        runtime=_RuntimeStub(fail=True),
        session_manager=manager,
        hook_runner=HookRunner(registry=hooks),
    )

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
    _wait_for(lambda: len(observed_events) == 1)
    assert observed_events == [
        {
            "session_id": session.session_id,
            "run_id": submitted.run_id,
            "error": failed.error,
        }
    ]


def test_runs_registry_dispatches_run_timeout_observe_hook_when_runtime_times_out(tmp_path: Path) -> None:
    observed_events: list[dict[str, object]] = []
    hooks = HookRegistry()

    async def on_run_timeout(event, ctx):
        del ctx
        observed_events.append(dict(event))

    hooks.on("run_timeout", on_run_timeout)

    store = SQLiteSessionStore(db_path=tmp_path / "runs-registry-run-timeout-hook.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    registry = RunsRegistry(
        runtime=_RuntimeStub(timeout=True),
        session_manager=manager,
        hook_runner=HookRunner(registry=hooks),
    )

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
    assert failed.error["code"] == "run_timeout"
    assert failed.stop_reason == "timeout"
    _wait_for(lambda: len(observed_events) == 1)
    assert observed_events == [
        {
            "session_id": session.session_id,
            "run_id": submitted.run_id,
            "error": failed.error,
        }
    ]


def test_runs_registry_marks_failed_on_retryable_model_error_without_retry(
    tmp_path: Path,
) -> None:
    """After M251 retry is handled in loop; retryable ModelError from runtime.run() marks run failed.

    The registry no longer contains a while-True retry loop. Any ModelError that
    propagates out of runtime.run() (including retryable=True) is treated as terminal.
    """
    store = SQLiteSessionStore(db_path=tmp_path / "runs-registry-retry.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    registry = RunsRegistry(runtime=_RetryableModelErrorRuntime(), session_manager=manager)

    submitted = registry.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": "retry me"}],
    )

    _wait_for(
        lambda: registry.get(submitted.run_id) is not None
        and registry.get(submitted.run_id).status in {RunStatus.FAILED, RunStatus.COMPLETED},
        timeout_seconds=2.0,
    )

    final = registry.get(submitted.run_id)
    assert final is not None
    assert final.status is RunStatus.FAILED

    entries = manager.list_entries(session.session_id)
    run_statuses = [
        event.data["status"]
        for event in entries
        if getattr(event.kind, "value", "") == "session.run.status"
        and event.data.get("run_id") == submitted.run_id
    ]
    # Should transition queued -> running -> failed with no retry-running entries
    assert run_statuses[-1] == "failed"
    retry_attempts = [e for e in entries if e.data.get("attempt") is not None]
    assert retry_attempts == [], "registry must not emit retry attempt entries after M251"
