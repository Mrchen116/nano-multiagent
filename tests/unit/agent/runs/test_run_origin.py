"""Unit tests for RunOrigin schema and registry propagation."""

import asyncio
from pathlib import Path
from typing import Any, Sequence

import pytest

from agent.core.runs.origin import RunOrigin
from agent.core.runs.registry import RunRecord, RunStatus, RunsRegistry
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.core.types import Message, TurnResult


class _RuntimeStub:
    async def run(
        self,
        session_id,
        parts,
        *,
        stream=True,
        run_id=None,
        controller=None,
        workspace_root=None,
    ):  # noqa: ANN001, ANN201
        del parts, stream, run_id, controller
        return TurnResult(
            session_id=session_id,
            turn_id="turn_1",
            messages=(Message(message_id="msg_1", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


class _CapturingRuntimeStub:
    """Captures kwargs passed to runtime.run for inspection."""

    def __init__(self) -> None:
        self.captured_kwargs: dict[str, Any] = {}

    async def run(  # noqa: ANN201
        self,
        session_id: str,
        parts: Sequence[Any],
        *,
        stream: bool = True,
        run_id: str | None = None,
        controller: Any = None,
        origin: "RunOrigin | None" = None,
        workspace_root: Any = None,
        model: str | None = None,
    ) -> TurnResult:
        self.captured_kwargs = {
            "stream": stream,
            "run_id": run_id,
            "origin": origin,
            "workspace_root": workspace_root,
            "model": model,
        }
        return TurnResult(
            session_id=session_id,
            turn_id="turn_cap",
            messages=(Message(message_id="msg_cap", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


def test_run_origin_enum_values() -> None:
    assert RunOrigin.USER == "user"
    assert RunOrigin.BACKGROUND_TASK == "background_task"
    assert RunOrigin.HEARTBEAT == "heartbeat"


def test_run_record_defaults() -> None:
    record = RunRecord(
        run_id="run_1",
        session_id="sess_1",
        status=RunStatus.QUEUED,
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
    )
    assert record.origin is RunOrigin.USER
    assert record.source_task_id is None


def test_run_record_explicit_origin() -> None:
    record = RunRecord(
        run_id="run_1",
        session_id="sess_1",
        status=RunStatus.QUEUED,
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
        origin=RunOrigin.BACKGROUND_TASK,
        source_task_id="task_123",
    )
    assert record.origin is RunOrigin.BACKGROUND_TASK
    assert record.source_task_id == "task_123"


def test_submit_propagates_origin_and_source_task_id(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_RuntimeStub(), session_manager=manager)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            origin=RunOrigin.BACKGROUND_TASK,
            source_task_id="task_456",
        )
        assert submitted.origin is RunOrigin.BACKGROUND_TASK
        assert submitted.source_task_id == "task_456"
    finally:
        registry.shutdown()


def test_submit_defaults_to_user_origin(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_RuntimeStub(), session_manager=manager)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
        )
        assert submitted.origin is RunOrigin.USER
        assert submitted.source_task_id is None
    finally:
        registry.shutdown()


# ---------------------------------------------------------------------------
# R4: RunRecord.origin thread-through to runtime.run (feat-333-M1)
# ---------------------------------------------------------------------------


def test_submit_threads_origin_to_runtime_run(tmp_path: Path) -> None:
    """RunsRegistry._run_worker_async must pass origin to runtime.run()."""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    runtime_stub = _CapturingRuntimeStub()
    registry = RunsRegistry(runtime=runtime_stub, session_manager=manager)

    try:
        registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "heartbeat task"}],
            origin=RunOrigin.HEARTBEAT,
        )
        # Wait for the async worker to complete
        import time

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if runtime_stub.captured_kwargs:
                break
            time.sleep(0.05)
    finally:
        registry.shutdown()

    # runtime.run must have been called with origin=RunOrigin.HEARTBEAT
    assert runtime_stub.captured_kwargs.get("origin") is RunOrigin.HEARTBEAT
