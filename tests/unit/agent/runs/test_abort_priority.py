"""Unit tests for priority=now preemption → cancelled terminal status."""

import time
from pathlib import Path

from agent.core.runs.registry import RunStatus, RunsRegistry
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.core.types import Message, TurnResult


class _RuntimeAbortedStub:
    """Runtime that simulates a run aborted by priority=now preemption."""

    async def run(self, session_id, parts, *, stream=True, run_id=None, controller=None):  # noqa: ANN001, ANN201
        del parts, stream, run_id, controller
        return TurnResult(
            session_id=session_id,
            turn_id="turn_aborted",
            messages=(
                Message(message_id="msg_aborted", role="turn_meta", content="", metadata={"stop_reason": "aborted"}),
            ),
            completed=False,
            stop_reason="aborted",
        )


def _wait_for(predicate, *, timeout_seconds: float = 2.0):  # noqa: ANN001
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met before timeout")


def test_aborted_run_gets_cancelled_status(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(runtime=_RuntimeAbortedStub(), session_manager=manager)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
        )
        _wait_for(
            lambda: registry.get(submitted.run_id) is not None
            and registry.get(submitted.run_id).status in {RunStatus.CANCELLED, RunStatus.COMPLETED},
            timeout_seconds=2.0,
        )

        final = registry.get(submitted.run_id)
        assert final is not None
        assert final.status is RunStatus.CANCELLED
        assert final.stop_reason == "aborted"
        assert final.error is not None
        assert final.error["code"] == "run_aborted_by_priority_now"
        assert final.error["retryable"] is False
    finally:
        registry.shutdown()
