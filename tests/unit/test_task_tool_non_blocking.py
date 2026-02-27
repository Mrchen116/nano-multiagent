import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from nano_multiagent.core.errors import ToolError
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.builtins.task import TaskTool


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0
        self.run_calls: list[dict[str, object]] = []
        self.continue_calls: list[dict[str, object]] = []

    def create_session(self) -> _Session:
        self.created += 1
        return _Session(session_id=f"sess_task_non_blocking_{self.created}")

    def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        self.run_calls.append(
            {
                "session_id": session_id,
                "parts": parts,
                "stream": stream,
                "llm_session_id": llm_session_id,
            }
        )
        time.sleep(0.05)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_non_blocking",
            messages=(Message(message_id="msg_non_blocking", role="assistant", content="done"),),
            completed=True,
            stop_reason="completed",
        )

    def continue_turn(
        self,
        session_id: str,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        self.continue_calls.append(
            {
                "session_id": session_id,
                "stream": stream,
                "llm_session_id": llm_session_id,
            }
        )
        return TurnResult(
            session_id=session_id,
            turn_id="turn_continue",
            messages=(Message(message_id="msg_continue", role="assistant", content="continued"),),
            completed=True,
            stop_reason="completed",
        )


def _context(tmp_path: Path) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path).with_session("sess_main_unit")


def _wait_for(predicate, *, timeout_seconds: float = 0.5) -> None:  # noqa: ANN001
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met before timeout")


def test_task_non_blocking_returns_receipt_and_executes_in_background(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    result = tool.run({"mode": "non_blocking", "prompt": "run later"}, _context(tmp_path))

    assert result["mode"] == "non_blocking"
    assert result["status"] == "queued"
    assert result["task_id"].startswith("call_")
    assert result["session_id"] == "sess_task_non_blocking_1"
    _wait_for(lambda: len(runtime.run_calls) == 1)


def test_task_idempotency_key_returns_same_receipt(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)
    args = {"mode": "non_blocking", "prompt": "same task", "idempotency_key": "idem-1"}

    first = tool.run(args, _context(tmp_path))
    second = tool.run(args, _context(tmp_path))

    assert first["task_id"] == second["task_id"]
    assert second["idempotent_replay"] is True


def test_task_rejects_new_task_when_category_and_subagent_type_both_present(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    with pytest.raises(ToolError, match="category and subagent_type are mutually exclusive"):
        tool.run(
            {
                "mode": "blocking",
                "prompt": "do work",
                "category": "ops",
                "subagent_type": "planner",
            },
            _context(tmp_path),
        )


def test_task_continuation_uses_existing_session_id(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    result = tool.run({"mode": "blocking", "session_id": "sess_existing"}, _context(tmp_path))

    assert result["status"] == "completed"
    assert result["continuation"] is True
    assert result["session_id"] == "sess_existing"
    assert runtime.continue_calls[0]["session_id"] == "sess_existing"
    assert runtime.created == 0
