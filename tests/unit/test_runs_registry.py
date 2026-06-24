import time
from pathlib import Path

from agent.core.errors import ModelError
from agent.core.types import Message, TokenUsage, TurnResult
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.runs.registry import RunStatus, RunsRegistry, _RegistryState
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager


class _RuntimeStub:
    def __init__(self, *, fail: bool = False, timeout: bool = False) -> None:
        self._fail = fail
        self._timeout = timeout

    async def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        run_id: str | None = None,
        controller=None,
        workspace_root=None,
        origin=None,
        model=None,
    ):  # noqa: ANN001, ANN201
        del parts
        del stream
        del origin
        del workspace_root
        if self._timeout:
            raise TimeoutError("runtime timed out")
        if self._fail:
            raise RuntimeError("runtime boom")
        return TurnResult(
            session_id=session_id,
            turn_id="turn_async_unit",
            messages=(
                Message(message_id="msg_async_unit", role="assistant", content="ok"),
            ),
            completed=True,
            stop_reason="completed",
        )


class _RuntimeWithUsageStub:
    async def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        run_id: str | None = None,
        controller=None,
        workspace_root=None,
        origin=None,
        model=None,
    ):  # noqa: ANN001, ANN201
        del parts
        del stream
        del origin
        del workspace_root
        return TurnResult(
            session_id=session_id,
            turn_id="turn_async_usage",
            messages=(
                Message(message_id="msg_async_usage", role="assistant", content="ok"),
            ),
            completed=True,
            stop_reason="completed",
            usage=TokenUsage(prompt_tokens=200, completion_tokens=20, total_tokens=220),
        )


class _RetryableModelErrorRuntime:
    """Runtime that raises a retryable ModelError, simulating loop-exhausted errors reaching registry."""

    async def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        run_id: str | None = None,
        controller=None,
        workspace_root=None,
        origin=None,
        model=None,
    ):  # noqa: ANN001, ANN201
        del session_id, parts, stream, run_id, origin, workspace_root
        # After M251 retry lives in loop; retryable errors that reach registry are terminal.
        raise ModelError("transient upstream blip", retryable=True)


class _RuntimeCapturingModel:
    """Records the ``model`` it is asked to run with (bugfix-429 R1)."""

    def __init__(self) -> None:
        self.models: list[object] = []

    async def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        run_id: str | None = None,
        controller=None,
        workspace_root=None,
        origin=None,
        model=None,
    ):  # noqa: ANN001, ANN201
        del parts, stream, run_id, controller, workspace_root, origin
        self.models.append(model)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_model_capture",
            messages=(
                Message(message_id="msg_model_capture", role="assistant", content="ok"),
            ),
            completed=True,
            stop_reason="completed",
        )


def test_runs_registry_threads_model_into_record_and_runtime(tmp_path: Path) -> None:
    """bugfix-429 R1: submit(model=X) stores RunRecord.model and runtime.run gets X.

    submit is async-queued (background create_task) so model cannot be a plain
    sync pass-through — it must live on RunRecord for the background worker.
    """
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    runtime = _RuntimeCapturingModel()
    registry = RunsRegistry(runtime=runtime, session_manager=manager)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            model="codex_oauth:gpt-5.5",
        )
        assert submitted.model == "codex_oauth:gpt-5.5"

        _wait_for(lambda: len(runtime.models) >= 1)
        assert runtime.models[0] == "codex_oauth:gpt-5.5"
    finally:
        registry.shutdown()


def _wait_for(predicate, *, timeout_seconds: float = 1.0) -> None:  # noqa: ANN001
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met before timeout")


def test_runs_registry_transitions_status_entries(tmp_path: Path) -> None:
    """Run status transitions through registry memory; JSONL does not persist RUN_STATUS."""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_RuntimeStub(), session_manager=manager)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
        )

        assert submitted.status is RunStatus.QUEUED

        _wait_for(
            lambda: (
                registry.get(submitted.run_id) is not None
                and registry.get(submitted.run_id).status is RunStatus.COMPLETED
            )
        )
        completed = registry.get(submitted.run_id)
        assert completed is not None
        assert completed.turn_id == "turn_async_unit"
        assert completed.output_text == "ok"

        # RUN_STATUS is not persisted in JSONL architecture
        entries = manager.list_entries(session.session_id)
        run_statuses = [
            event.data["status"]
            for event in entries
            if getattr(event.kind, "value", "") == "session.run.status"
        ]
        assert run_statuses == []
    finally:
        registry.shutdown()


def test_runs_registry_marks_failed_when_runtime_raises(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_RuntimeStub(fail=True), session_manager=manager)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
        )
        _wait_for(
            lambda: (
                registry.get(submitted.run_id) is not None
                and registry.get(submitted.run_id).status is RunStatus.FAILED
            )
        )

        failed = registry.get(submitted.run_id)
        assert failed is not None
        assert failed.error is not None
        assert failed.error["message"] == "runtime boom"
    finally:
        registry.shutdown()


def test_runs_registry_tracks_completed_run_usage(tmp_path: Path) -> None:
    """Registry tracks usage in memory; JSONL does not persist RUN_STATUS."""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_RuntimeWithUsageStub(), session_manager=manager)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
        )
        _wait_for(
            lambda: (
                registry.get(submitted.run_id) is not None
                and registry.get(submitted.run_id).status is RunStatus.COMPLETED
            )
        )

        completed = registry.get(submitted.run_id)
        assert completed is not None
        assert completed.usage is not None
        assert completed.usage.total_tokens == 220

        # RUN_STATUS is not persisted in JSONL architecture
        entries = manager.list_entries(session.session_id)
        completed_entries = [
            event
            for event in entries
            if getattr(event.kind, "value", "") == "session.run.status"
            and event.data.get("status") == "completed"
        ]
        assert completed_entries == []
    finally:
        registry.shutdown()


def test_runs_registry_dispatches_run_error_observe_hook_when_runtime_raises(
    tmp_path: Path,
) -> None:
    observed_events: list[dict[str, object]] = []
    hooks = HookRegistry()

    async def on_run_error(event, ctx):
        del ctx
        observed_events.append(dict(event))

    hooks.on("run_error", on_run_error)

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(
        runtime=_RuntimeStub(fail=True),
        session_manager=manager,
        hook_runner=HookRunner(registry=hooks),
    )

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
        )
        _wait_for(
            lambda: (
                registry.get(submitted.run_id) is not None
                and registry.get(submitted.run_id).status is RunStatus.FAILED
            )
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
    finally:
        registry.shutdown()


def test_runs_registry_dispatches_run_timeout_observe_hook_when_runtime_times_out(
    tmp_path: Path,
) -> None:
    observed_events: list[dict[str, object]] = []
    hooks = HookRegistry()

    async def on_run_timeout(event, ctx):
        del ctx
        observed_events.append(dict(event))

    hooks.on("run_timeout", on_run_timeout)

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(
        runtime=_RuntimeStub(timeout=True),
        session_manager=manager,
        hook_runner=HookRunner(registry=hooks),
    )

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
        )
        _wait_for(
            lambda: (
                registry.get(submitted.run_id) is not None
                and registry.get(submitted.run_id).status is RunStatus.FAILED
            )
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
    finally:
        registry.shutdown()


def test_runs_registry_marks_failed_on_retryable_model_error_without_retry(
    tmp_path: Path,
) -> None:
    """After M251 retry is handled in loop; retryable ModelError from runtime.run() marks run failed.

    The registry no longer contains a while-True retry loop. Any ModelError that
    propagates out of runtime.run() (including retryable=True) is treated as terminal.
    """
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(
        runtime=_RetryableModelErrorRuntime(), session_manager=manager
    )

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "retry me"}],
        )

        _wait_for(
            lambda: (
                registry.get(submitted.run_id) is not None
                and registry.get(submitted.run_id).status
                in {RunStatus.FAILED, RunStatus.COMPLETED}
            ),
            timeout_seconds=2.0,
        )

        final = registry.get(submitted.run_id)
        assert final is not None
        assert final.status is RunStatus.FAILED

        # RUN_STATUS is not persisted in JSONL architecture
        entries = manager.list_entries(session.session_id)
        run_statuses = [
            event.data["status"]
            for event in entries
            if getattr(event.kind, "value", "") == "session.run.status"
            and event.data.get("run_id") == submitted.run_id
        ]
        assert run_statuses == []
        retry_attempts = [e for e in entries if e.data.get("attempt") is not None]
        assert retry_attempts == [], (
            "registry must not emit retry attempt entries after M251"
        )
    finally:
        registry.shutdown()


# ---------------------------------------------------------------------------
# bugfix-402-M3: R1 — Task 登记 + DRAINING 状态机
# ---------------------------------------------------------------------------

import asyncio as _asyncio


def test_registry_submit_rejected_after_shutdown(tmp_path: Path) -> None:
    """submit() after shutdown must raise RegistryClosedError immediately."""
    from agent.core.runs.registry import RegistryClosedError

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_RuntimeStub(), session_manager=manager)
    registry.shutdown()

    import pytest

    with pytest.raises(RegistryClosedError):
        registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "too late"}],
        )


def test_registry_submit_rejected_after_shutdown_begins(tmp_path: Path) -> None:
    """begin_shutdown() must reject new runs before the blocking drain starts."""
    from agent.core.runs.registry import RegistryClosedError

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_RuntimeStub(), session_manager=manager)

    registry.begin_shutdown()

    import pytest

    with pytest.raises(RegistryClosedError):
        registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "too late"}],
        )
    registry.shutdown()


def test_registry_does_not_register_task_after_shutdown_begins(
    tmp_path: Path,
) -> None:
    """A submit already queued onto the loop must become terminal during drain."""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_RuntimeStub(), session_manager=manager)
    loop = registry.get_event_loop()
    original_call_soon = loop.call_soon_threadsafe
    scheduled: list[object] = []

    def _defer(callback, *args):  # noqa: ANN001
        scheduled.append((callback, args))

    loop.call_soon_threadsafe = _defer
    submitted = registry.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": "racing submit"}],
    )
    registry.begin_shutdown()
    callback, args = scheduled.pop()
    callback(*args)
    loop.call_soon_threadsafe = original_call_soon

    final = registry.get(submitted.run_id)
    assert final is not None
    assert final.status is RunStatus.CANCELLED
    assert final.stop_reason == "shutdown"
    registry.shutdown()


def test_registry_drains_active_task_before_loop_stops(tmp_path: Path) -> None:
    """shutdown() must wait for all running Tasks to reach terminal state before stopping loop."""
    import threading

    gate_holder: list[_asyncio.Event] = []
    # Signal fired by _GatedRuntime.run() as soon as it enters (i.e. the run is
    # RUNNING on the loop).  The main thread waits on this before calling shutdown()
    # to avoid the race where drain snapshots the run while it is still QUEUED and
    # cancels it immediately — that is correct registry behaviour, not the drain bug
    # this test is meant to exercise.
    started = threading.Event()

    class _GatedRuntime:
        async def run(
            self,
            session_id: str,
            parts,
            *,
            stream: bool = True,
            run_id: str | None = None,
            controller=None,
            workspace_root=None,
            origin=None,
            model=None,
        ):  # noqa: ANN001, ANN201
            started.set()  # notify main thread: we are inside run(), status is RUNNING
            await gate_holder[0].wait()
            return TurnResult(
                session_id=session_id,
                turn_id="turn_gated",
                messages=(
                    Message(message_id="msg_gated", role="assistant", content="done"),
                ),
                completed=True,
                stop_reason="completed",
            )

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_GatedRuntime(), session_manager=manager)

    # Create an asyncio.Event on registry's dedicated loop so it is compatible.
    loop = registry.get_event_loop()
    ev_future = _asyncio.run_coroutine_threadsafe(_create_asyncio_event(), loop)
    ev = ev_future.result(timeout=2.0)
    gate_holder.append(ev)

    submitted = registry.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": "gated"}],
    )

    # Wait until _GatedRuntime.run() has been entered (run is RUNNING) before
    # triggering shutdown.  This is the deterministic synchronisation point that
    # prevents the race where drain snapshots the run while it is still QUEUED.
    assert started.wait(timeout=5.0), "timed out waiting for run to enter RUNNING"

    # Release the gate only after drain has begun, so the test definitely exercises
    # the "drain blocks waiting for a RUNNING task" path rather than "task already
    # completed before drain snapshot".  Polling registry._state is safe: the field
    # transitions OPEN → DRAINING inside begin_shutdown() (under self._lock) before
    # _drain_and_stop is scheduled on the loop, so DRAINING is visible from any
    # thread the moment shutdown() passes begin_shutdown().  The short poll sleep is
    # a condition-based wait, not a timing heuristic.
    def _release_after_drain_starts() -> None:
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if registry._state is _RegistryState.DRAINING:  # noqa: SLF001
                break
            time.sleep(0.001)
        _asyncio.run_coroutine_threadsafe(_set_event(ev), loop)

    releaser = threading.Thread(target=_release_after_drain_starts, daemon=True)
    releaser.start()

    registry.shutdown()  # must block until gated task completes
    releaser.join(timeout=2.0)

    final = registry.get(submitted.run_id)
    assert final is not None
    assert final.status is RunStatus.COMPLETED, (
        f"expected COMPLETED, got {final.status}"
    )


def test_registry_force_cancel_marks_terminal_and_recovers_session(
    tmp_path: Path,
) -> None:
    """A run that exceeds shutdown grace must not remain RUNNING."""
    import asyncio
    from unittest.mock import MagicMock

    class _NeverEndingRuntime:
        def __init__(self) -> None:
            self.invalidated_sessions: list[str] = []

        async def run(
            self,
            session_id: str,
            parts,
            *,
            stream: bool = True,
            run_id: str | None = None,
            controller=None,
            workspace_root=None,
            origin=None,
            model=None,
        ):  # noqa: ANN001, ANN201
            del parts, stream, run_id, controller, workspace_root, origin
            await asyncio.Event().wait()

        def invalidate_session_cache(self, session_id: str) -> None:
            self.invalidated_sessions.append(session_id)

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    manager.prepare_transcript_for_run = MagicMock(
        wraps=manager.prepare_transcript_for_run
    )
    runtime = _NeverEndingRuntime()
    registry = RunsRegistry(
        runtime=runtime,
        session_manager=manager,
        drain_timeout_seconds=0.01,
    )

    submitted = registry.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": "block forever"}],
        workspace_root=tmp_path,
    )
    _wait_for(lambda: registry.get(submitted.run_id).status is RunStatus.RUNNING)

    registry.shutdown()

    final = registry.get(submitted.run_id)
    assert final is not None
    assert final.status is RunStatus.CANCELLED
    assert final.stop_reason == "shutdown"
    manager.prepare_transcript_for_run.assert_called_once_with(
        session.session_id,
        reason="shutdown",
        workspace_root=tmp_path,
    )
    assert runtime.invalidated_sessions == [session.session_id]


async def _create_asyncio_event() -> _asyncio.Event:
    return _asyncio.Event()


async def _set_event(ev: _asyncio.Event) -> None:
    ev.set()


def test_stranded_continuation_follows_injected_origin(tmp_path: Path) -> None:
    """The registry's terminal chokepoint re-runs a stranded steer as a continuation
    carrying its injection origin (USER), not the hardcoded BACKGROUND_TASK (决策3).

    Registry-isolation test: the gated runtime stands in for the loop and never
    drains the controller, so the steer is stranded and ``_settle_terminal_pending``
    re-submits it. This exercises the chokepoint's origin propagation directly.

    bugfix-426-M4 决策3 收窄: in production with the real loop, a NORMAL completion no
    longer reaches this stranded path — the loop's terminal re-drain (决策5) consumes
    the steer on the SAME run (see the kernel contract
    ``test_terminal_window_steer_continues_same_run_no_continuation``). This chokepoint
    now fires only for ABNORMAL terminations (watchdog/crash/timeout), covered on the
    real path by ``test_stranded_continuation_fires_on_non_user_cancel``. The stubbed
    ``completed=True`` runtime here is only the vehicle to reach the mechanism in
    isolation; it does not claim normal completion strands in production.
    """
    import threading

    from agent.core.llm.interfaces import LLMMessage
    from agent.core.runs.origin import RunOrigin

    gate_holder: list[_asyncio.Event] = []
    started = threading.Event()

    class _GatedRuntime:
        async def run(
            self,
            session_id: str,
            parts,
            *,
            stream: bool = True,
            run_id: str | None = None,
            controller=None,
            workspace_root=None,
            origin=None,
            model=None,
        ):  # noqa: ANN001, ANN201
            del parts, stream, run_id, controller, workspace_root, origin, model
            started.set()
            await gate_holder[0].wait()
            return TurnResult(
                session_id=session_id,
                turn_id="turn_gated_inject",
                messages=(Message(message_id="m_g", role="assistant", content="ok"),),
                completed=True,
                stop_reason="completed",
            )

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_GatedRuntime(), session_manager=manager)

    loop = registry.get_event_loop()
    ev = _asyncio.run_coroutine_threadsafe(_create_asyncio_event(), loop).result(
        timeout=2.0
    )
    gate_holder.append(ev)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=tmp_path,
        )
        assert started.wait(timeout=5.0), "run did not enter RUNNING"

        injected = registry.inject_pending_message(
            session.session_id,
            LLMMessage(role="user", content="steered mid-run"),
            origin=RunOrigin.USER,
        )
        assert injected is True

        # Release the gate → run completes → terminal-path drain re-submits the
        # stranded message as a continuation run.
        _asyncio.run_coroutine_threadsafe(_set_event(ev), loop)

        def _continuation_origin():  # noqa: ANN202
            with registry._lock:  # noqa: SLF001
                for rid, rec in registry._runs.items():  # noqa: SLF001
                    if rid != submitted.run_id:
                        return rec.origin
            return None

        _wait_for(lambda: _continuation_origin() is not None, timeout_seconds=3.0)
        assert _continuation_origin() is RunOrigin.USER
    finally:
        registry.shutdown()


def _gated_registry(tmp_path: Path):  # noqa: ANN202
    """Build a registry whose runtime blocks on a loop-owned Event until released.

    Returns (registry, session, started_event, release_event). The run stays
    RUNNING until release_event is set, so a test can inject then terminate it via
    cancel()/interrupt() to exercise the non-completion terminal paths.
    """
    import threading

    started = threading.Event()
    gate_holder: list[_asyncio.Event] = []

    class _GatedRuntime:
        async def run(
            self,
            session_id: str,
            parts,
            *,
            stream: bool = True,
            run_id: str | None = None,
            controller=None,
            workspace_root=None,
            origin=None,
            model=None,
        ):  # noqa: ANN001, ANN201
            del parts, stream, run_id, workspace_root, origin, model
            started.set()
            await gate_holder[0].wait()
            # After release: honour an abort flag so a user /stop terminates as
            # aborted (mirrors the loop's cooperative abort handling).
            stop_reason = (
                "aborted"
                if controller is not None and controller.is_aborted
                else "completed"
            )
            return TurnResult(
                session_id=session_id,
                turn_id="turn_gated_term",
                messages=(Message(message_id="m_t", role="assistant", content="ok"),),
                completed=stop_reason == "completed",
                stop_reason=stop_reason,
            )

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_GatedRuntime(), session_manager=manager)
    loop = registry.get_event_loop()
    ev = _asyncio.run_coroutine_threadsafe(_create_asyncio_event(), loop).result(
        timeout=2.0
    )
    gate_holder.append(ev)
    return registry, session, started, ev


def test_stranded_continuation_fires_on_non_user_cancel(tmp_path: Path) -> None:
    """A message steered into a run that is then force-cancelled (watchdog idle
    reap / crash — NOT a user /stop) must survive: it re-runs as a continuation
    (bugfix-426 决策3 扩展 — covers the non-completion terminal path)."""
    from agent.core.llm.interfaces import LLMMessage
    from agent.core.runs.origin import RunOrigin

    registry, session, started, ev = _gated_registry(tmp_path)
    loop = registry.get_event_loop()
    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "long"}],
            workspace_root=tmp_path,
        )
        assert started.wait(timeout=5.0)
        assert (
            registry.inject_pending_message(
                session.session_id,
                LLMMessage(role="user", content="steered"),
                origin=RunOrigin.USER,
            )
            is True
        )
        # Force-cancel (non-user): mirrors the watchdog idle reap path.
        registry.cancel(submitted.run_id)

        def _continuation():  # noqa: ANN202
            with registry._lock:  # noqa: SLF001
                for rid, rec in registry._runs.items():  # noqa: SLF001
                    if rid != submitted.run_id:
                        return rec
            return None

        _wait_for(lambda: _continuation() is not None, timeout_seconds=3.0)
        assert _continuation().origin is RunOrigin.USER
        # Release the gate so the continuation run completes promptly (otherwise it
        # would block on the never-set Event and stall shutdown's drain).
        _asyncio.run_coroutine_threadsafe(_set_event(ev), loop)
    finally:
        registry.shutdown()


def test_user_stop_holds_pending_then_flushes_on_next_submit(tmp_path: Path) -> None:
    """A user /stop (abort user_initiated) does NOT auto-continue the stranded
    message, but does NOT discard it either: it is parked to the session held
    buffer and prepended to the session's NEXT submit (bugfix-426 决策3 /stop 语义)."""
    from agent.core.llm.interfaces import LLMMessage
    from agent.core.runs.origin import RunOrigin

    registry, session, started, ev = _gated_registry(tmp_path)
    loop = registry.get_event_loop()
    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "long"}],
            workspace_root=tmp_path,
        )
        assert started.wait(timeout=5.0)
        assert (
            registry.inject_pending_message(
                session.session_id,
                LLMMessage(role="user", content="steered after stop"),
                origin=RunOrigin.USER,
            )
            is True
        )
        # User /stop: sets abort(user_initiated=True). No foreground tool here, so
        # the run unwinds when we release the gate, returning aborted.
        interrupted = registry.interrupt(session.session_id)
        assert interrupted == submitted.run_id
        _asyncio.run_coroutine_threadsafe(_set_event(ev), loop)

        _wait_for(
            lambda: (
                registry.get(submitted.run_id) is not None
                and registry.get(submitted.run_id).status
                in {RunStatus.CANCELLED, RunStatus.COMPLETED}
            ),
            timeout_seconds=3.0,
        )
        # /stop must NOT auto-spawn a continuation run...
        time.sleep(0.2)
        with registry._lock:  # noqa: SLF001
            other_runs = [rid for rid in registry._runs if rid != submitted.run_id]
        assert other_runs == [], "user /stop must not auto-continue"
        # ...but the message must be held (not discarded).
        with registry._lock:  # noqa: SLF001
            assert [
                p.message.content for p in registry._held_pending[session.session_id]
            ] == ["steered after stop"]

        # Next submit for this session flushes the held buffer, prepended (FIFO:
        # held first, then this turn's parts).
        _asyncio.run_coroutine_threadsafe(_set_event(ev), loop)  # keep gate open
        next_run = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "msg3 new"}],
            workspace_root=tmp_path,
        )
        _wait_for(
            lambda: (
                registry.get(next_run.run_id) is not None
                and registry.get(next_run.run_id).status
                in {RunStatus.COMPLETED, RunStatus.CANCELLED, RunStatus.FAILED}
            ),
            timeout_seconds=3.0,
        )
        # Held buffer cleared after the flush.
        with registry._lock:  # noqa: SLF001
            assert session.session_id not in registry._held_pending
    finally:
        registry.shutdown()


def test_interrupt_holds_pending_synchronously(tmp_path: Path) -> None:
    """interrupt() (user /stop) parks unconsumed pending to held SYNCHRONOUSLY,
    before it returns — so the gateway's immediately-following synthetic /stop
    submit sees the held buffer already populated (bugfix-426 决策3 B, race fix)."""
    from agent.core.llm.interfaces import LLMMessage
    from agent.core.runs.origin import RunOrigin

    registry, session, started, ev = _gated_registry(tmp_path)
    loop = registry.get_event_loop()
    try:
        registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "long"}],
            workspace_root=tmp_path,
        )
        assert started.wait(timeout=5.0)
        registry.inject_pending_message(
            session.session_id,
            LLMMessage(role="user", content="held-sync"),
            origin=RunOrigin.USER,
        )
        # interrupt() returns: held must ALREADY be populated (synchronous), not
        # waiting for the carrier Task to unwind on the bg loop.
        registry.interrupt(session.session_id)
        with registry._lock:  # noqa: SLF001
            assert [
                p.message.content for p in registry._held_pending[session.session_id]
            ] == ["held-sync"]
        _asyncio.run_coroutine_threadsafe(_set_event(ev), loop)
    finally:
        registry.shutdown()


def test_submit_flush_held_false_does_not_consume_held(tmp_path: Path) -> None:
    """A submit with flush_held=False (the /stop synthetic bookkeeping turn) must
    NOT consume the held buffer; the next flush_held=True submit then carries it
    (bugfix-426 决策3 A, /stop synthetic-submit race fix)."""
    from agent.core.agent.run_control import PendingMessage
    from agent.core.llm.interfaces import LLMMessage
    from agent.core.runs.origin import RunOrigin

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_RuntimeStub(), session_manager=manager)
    try:
        with registry._lock:  # noqa: SLF001
            registry._held_pending[session.session_id] = [
                PendingMessage(
                    message=LLMMessage(role="user", content="held-x"),
                    origin=RunOrigin.USER,
                )
            ]
        # flush_held=False (synthetic /stop turn): held survives.
        registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "用户发送了 /stop 命令"}],
            workspace_root=tmp_path,
            flush_held=False,
        )
        with registry._lock:  # noqa: SLF001
            assert [
                p.message.content for p in registry._held_pending[session.session_id]
            ] == ["held-x"]
        # Next real submit (flush_held default True): held consumed + cleared.
        registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "msg3"}],
            workspace_root=tmp_path,
        )
        with registry._lock:  # noqa: SLF001
            assert session.session_id not in registry._held_pending
    finally:
        registry.shutdown()


def test_held_pending_prepended_in_fifo_order(tmp_path: Path) -> None:
    """The held flush prepends held messages before the new turn's parts (FIFO).

    Verified at the submit() boundary by capturing the parts the runtime receives.
    """
    import threading

    from agent.core.agent.run_control import PendingMessage
    from agent.core.llm.interfaces import LLMMessage
    from agent.core.runs.origin import RunOrigin

    captured: list[list[dict]] = []
    done = threading.Event()

    class _CapturingRuntime:
        async def run(
            self,
            session_id,
            parts,
            *,
            stream=True,
            run_id=None,
            controller=None,
            workspace_root=None,
            origin=None,
            model=None,
        ):  # noqa: ANN001, ANN201
            del stream, run_id, controller, workspace_root, origin, model
            captured.append([dict(p) for p in parts])
            done.set()
            return TurnResult(
                session_id=session_id,
                turn_id="t_cap",
                messages=(Message(message_id="m", role="assistant", content="ok"),),
                completed=True,
                stop_reason="completed",
            )

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_CapturingRuntime(), session_manager=manager)
    try:
        # Seed the held buffer directly (held is normally populated by a /stop).
        with registry._lock:  # noqa: SLF001
            registry._held_pending[session.session_id] = [
                PendingMessage(
                    message=LLMMessage(role="user", content="held-1"),
                    origin=RunOrigin.USER,
                ),
                PendingMessage(
                    message=LLMMessage(role="user", content="held-2"),
                    origin=RunOrigin.USER,
                ),
            ]
        registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "new-turn"}],
            workspace_root=tmp_path,
        )
        assert done.wait(timeout=3.0)
        texts = [p.get("text") for p in captured[0]]
        assert texts == ["held-1", "held-2", "new-turn"]
    finally:
        registry.shutdown()
