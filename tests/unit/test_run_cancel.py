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
            messages=(
                Message(message_id="msg_cancel_unit", role="assistant", content="ok"),
            ),
            completed=True,
            stop_reason="completed",
        )


class _AbortableBlockingRuntime:
    """Runtime that checks controller.is_aborted and exits early."""

    def __init__(self) -> None:
        self.started = Event()

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
        self.started.set()
        # Poll abort signal with short sleeps
        for _ in range(50):
            if controller is not None and controller.is_aborted:
                return TurnResult(
                    session_id="sess_abort_unit",
                    turn_id="turn_abort_unit",
                    messages=(
                        Message(
                            message_id="msg_abort",
                            role="assistant",
                            content="interrupted",
                        ),
                    ),
                    completed=False,
                    stop_reason="aborted",
                )
            await asyncio.sleep(0.01)
        return TurnResult(
            session_id="sess_abort_unit",
            turn_id="turn_abort_unit",
            messages=(
                Message(message_id="msg_timeout", role="assistant", content="ok"),
            ),
            completed=True,
            stop_reason="completed",
        )


class _FailureRuntime:
    """Runtime that raises a non-retryable ModelError (simulates loop exhausting retries)."""

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
        # Retryable errors are exhausted inside loop; what reaches registry is non-retryable.
        raise ModelError("retries exhausted", retryable=False)


class _SessionLockParkedRuntime:
    """Runtime that mirrors the production per-session-lock failure mode (#110).

    Like the real runtime, every turn executes inside ``async with`` a
    per-session ``asyncio.Lock`` and then parks on an awaitable that never
    resolves on its own (standing in for a tool/LLM/permission await the
    cooperative cancel flag cannot reach). The lock is therefore held until the
    carrier Task is *force* cancelled — exactly the invariant M1 must restore.
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self.entered = Event()
        self.second_completed = Event()
        self._first_seen = False

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
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            if not self._first_seen:
                # First run: hold the lock and park forever. Only a force
                # cancel of the carrier Task can break this await and release
                # the lock via the CancelledError path.
                self._first_seen = True
                self.entered.set()
                await asyncio.Event().wait()
            # Second run: reaching here proves the lock was released, i.e. the
            # parked first run no longer permanently blocks the session.
            self.second_completed.set()
            return TurnResult(
                session_id=session_id,
                turn_id="turn_second",
                messages=(
                    Message(message_id="msg_second", role="assistant", content="ok"),
                ),
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


def test_cancel_force_releases_session_lock_so_next_run_proceeds(
    tmp_path: Path,
) -> None:
    """P0 invariant (#110): cancelling a parked run releases the session lock.

    Reproduces the incident chain: a run parked while holding the per-session
    lock must be *force* terminated by ``cancel(run_id)`` so the next run in the
    same session can acquire the lock and reach a terminal state — without
    rebuilding the kernel. With only the cooperative ``controller.cancel()``
    flag (pre-M1), the carrier Task keeps awaiting, the lock is never released,
    and the second run stays QUEUED forever (this assertion times out → RED).
    """
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    runtime = _SessionLockParkedRuntime()
    registry = RunsRegistry(runtime=runtime, session_manager=manager)

    try:
        first = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "park holding the lock"}],
            workspace_root=tmp_path,
        )
        _wait_for(lambda: runtime.entered.is_set(), timeout_seconds=2.0)

        # Second run queues behind the held lock; it cannot start until the
        # first run's lock is released.
        second = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "should proceed after cancel"}],
            workspace_root=tmp_path,
        )

        # Force cancel the parked first run.
        cancelled = registry.cancel(first.run_id)
        assert cancelled is not None
        assert cancelled.status is RunStatus.CANCELLED

        # The released lock lets the second run run to completion.
        _wait_for(
            lambda: registry.get(second.run_id).status is RunStatus.COMPLETED,
            timeout_seconds=3.0,
        )
        assert runtime.second_completed.is_set()
    finally:
        registry.shutdown()


def test_cancel_already_terminal_run_is_idempotent_noop(tmp_path: Path) -> None:
    """Cancelling a run with no live carrier Task is safe (idempotent).

    After a run has reached a terminal state its Task is gone from
    ``_owned_tasks``; the force-cancel branch must skip cleanly rather than
    error on a missing/completed Task.
    """
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    runtime = _FailureRuntime()
    registry = RunsRegistry(runtime=runtime, session_manager=manager)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "fail fast"}],
            workspace_root=tmp_path,
        )
        _wait_for(
            lambda: registry.get(submitted.run_id).status is RunStatus.FAILED,
            timeout_seconds=2.0,
        )

        # Run is already terminal (FAILED), Task removed from _owned_tasks.
        first = registry.cancel(submitted.run_id)
        second = registry.cancel(submitted.run_id)
        assert first is not None and first.status is RunStatus.FAILED
        assert second is not None and second.status is RunStatus.FAILED
    finally:
        registry.shutdown()


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
            lambda: (
                registry.get(submitted.run_id).status
                in {RunStatus.FAILED, RunStatus.COMPLETED, RunStatus.CANCELLED}
            ),
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
    registry = RunsRegistry(
        runtime=_AbortableBlockingRuntime(), session_manager=manager
    )

    try:
        assert registry.interrupt("sess_no_active") is None
    finally:
        registry.shutdown()


def test_interrupt_with_inflight_foreground_tool_force_cancels_carrier_task(
    tmp_path: Path,
) -> None:
    """bugfix-417-M5 (#114): when the active run is parked inside a blocking
    foreground tool (long shell command), cooperative abort alone cannot unwind
    the carrier Task — it is stuck on the tool's to_thread that never returns
    until the subprocess is killed. interrupt must (a) call the injected
    foreground_stopper to kill the subprocess tree and (b) force-cancel the
    carrier Task so the parked await unwinds and the session frees up.
    """
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    runtime = _SessionLockParkedRuntime()

    stopped_sessions: list[str] = []

    def _foreground_stopper(session_id: str) -> bool:
        # Stand in for "there IS an in-flight foreground tool for this session":
        # killpg the subprocess tree (recorded) and report True so the registry
        # knows to force-cancel the parked carrier Task.
        stopped_sessions.append(session_id)
        return True

    registry = RunsRegistry(
        runtime=runtime,
        session_manager=manager,
        foreground_stopper=_foreground_stopper,
    )

    try:
        first = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "park holding the lock"}],
            workspace_root=tmp_path,
        )
        _wait_for(lambda: runtime.entered.is_set(), timeout_seconds=2.0)

        second = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "should proceed after interrupt"}],
            workspace_root=tmp_path,
        )

        run_id = registry.interrupt(session.session_id)
        assert run_id == first.run_id
        # The foreground subprocess tree was killed for this session.
        assert stopped_sessions == [session.session_id]

        # Force-cancel released the lock → the second run runs to completion.
        _wait_for(
            lambda: registry.get(second.run_id).status is RunStatus.COMPLETED,
            timeout_seconds=3.0,
        )
        assert runtime.second_completed.is_set()
    finally:
        registry.shutdown()


def test_interrupt_without_inflight_foreground_tool_only_aborts(
    tmp_path: Path,
) -> None:
    """bugfix-417-M5 (#114): with NO in-flight foreground tool, interrupt must
    degrade to the pre-existing cooperative-abort behaviour (stop_reason=aborted),
    NOT force-cancel — preserving the existing /stop semantics for runs that are
    not wedged inside a blocking subprocess.
    """
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    runtime = _AbortableBlockingRuntime()

    def _foreground_stopper(session_id: str) -> bool:
        # No in-flight foreground tool for this session.
        return False

    registry = RunsRegistry(
        runtime=runtime,
        session_manager=manager,
        foreground_stopper=_foreground_stopper,
    )

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "interrupt me"}],
        )
        _wait_for(lambda: runtime.started.is_set())

        run_id = registry.interrupt(session.session_id)
        assert run_id == submitted.run_id

        _wait_for(
            lambda: registry.get(submitted.run_id).status is RunStatus.CANCELLED,
            timeout_seconds=2.0,
        )
        final = registry.get(submitted.run_id)
        assert final is not None
        # Cooperative abort path: the runtime observed is_aborted and returned a
        # graceful aborted TurnResult (NOT a force-cancel CancelledError).
        assert final.stop_reason == "aborted"
    finally:
        registry.shutdown()


def test_cancel_stops_inflight_foreground_tool(tmp_path: Path) -> None:
    """bugfix-417-M5 (#114): cancel(run_id) must also kill the in-flight
    foreground tool's subprocess tree (M1 already force-cancels the carrier Task
    to release the lock; M5 adds the subprocess reap so no orphan is left)."""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    runtime = _SessionLockParkedRuntime()

    stopped_sessions: list[str] = []

    def _foreground_stopper(session_id: str) -> bool:
        stopped_sessions.append(session_id)
        return True

    registry = RunsRegistry(
        runtime=runtime,
        session_manager=manager,
        foreground_stopper=_foreground_stopper,
    )

    try:
        first = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "park holding the lock"}],
            workspace_root=tmp_path,
        )
        _wait_for(lambda: runtime.entered.is_set(), timeout_seconds=2.0)

        cancelled = registry.cancel(first.run_id)
        assert cancelled is not None
        assert cancelled.status is RunStatus.CANCELLED
        assert stopped_sessions == [session.session_id]
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

        _wait_for(
            lambda: (
                registry.get(submitted.run_id).status
                in {RunStatus.FAILED, RunStatus.COMPLETED}
            ),
            timeout_seconds=2.0,
        )

        final = registry.get(submitted.run_id)
        assert final is not None
        assert final.status is RunStatus.FAILED
    finally:
        registry.shutdown()
