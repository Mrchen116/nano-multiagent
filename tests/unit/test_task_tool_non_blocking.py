import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.types import Message, TurnResult
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.task import TaskTool


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0
        self.run_calls: list[dict[str, object]] = []
        self.continue_calls: list[dict[str, object]] = []
        self._sessions: set[str] = {"sess_existing"}

    def create_session(self, *, title: str | None = None, metadata=None) -> _Session:
        del title, metadata
        self.created += 1
        session_id = f"sess_task_non_blocking_{self.created}"
        self._sessions.add(session_id)
        return _Session(session_id=session_id)

    def get_session(self, session_id: str) -> _Session | None:
        if session_id in self._sessions:
            return _Session(session_id=session_id)
        return None

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

    result = tool.run(
        {
            "run_in_background": True,
            "load_skills": [],
            "description": "delegate task",
            "prompt": "run later",
            "category": "research",
        },
        _context(tmp_path),
    )

    assert result.startswith("Background task launched.")
    assert "Task ID: call_" in result
    assert "Description: delegate task" in result
    assert "Agent: research (category: research)" in result
    assert "Status: queued" in result
    assert "<task_metadata>\nsession_id: sess_task_non_blocking_1\n</task_metadata>" in result
    _wait_for(lambda: len(runtime.run_calls) == 1)


def test_task_idempotency_key_returns_same_receipt(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)
    args = {
        "run_in_background": True,
        "load_skills": [],
        "description": "delegate task",
        "prompt": "same task",
        "category": "research",
        "idempotency_key": "idem-1",
    }

    first = tool.run(args, _context(tmp_path))
    second = tool.run(args, _context(tmp_path))

    assert first == second


def test_task_rejects_new_task_when_category_and_subagent_type_both_present(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    with pytest.raises(ToolError, match="category and subagent_type are mutually exclusive"):
        tool.run(
            {
                "run_in_background": False,
                "load_skills": [],
                "description": "delegate task",
                "prompt": "do work",
                "category": "ops",
                "subagent_type": "planner",
            },
            _context(tmp_path),
        )


def test_task_rejects_new_task_when_category_and_subagent_type_both_missing(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    with pytest.raises(ToolError, match="either category or subagent_type is required"):
        tool.run(
            {
                "run_in_background": False,
                "load_skills": [],
                "description": "delegate task",
                "prompt": "do work",
            },
            _context(tmp_path),
        )


def test_task_continuation_uses_existing_session_id(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    result = tool.run(
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "continue task",
            "prompt": "fix failing assertion",
            "session_id": "sess_existing",
        },
        _context(tmp_path),
    )

    assert result.startswith("Task continued and completed in ")
    assert "\n---\n\ndone\n" in result
    assert "<task_metadata>\nsession_id: sess_existing\n</task_metadata>" in result
    assert runtime.run_calls[0]["session_id"] == "sess_existing"
    assert runtime.created == 0


def test_task_unknown_session_id_starts_new_task_when_prompt_present(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    result = tool.run(
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "tell joke",
            "prompt": "讲个冷笑话",
            "session_id": "joke-subagent-1",
            "category": "conversation",
            "subagent_type": "default",
        },
        _context(tmp_path),
    )

    assert result.startswith("Task completed in ")
    assert "session_id: sess_task_non_blocking_1" in result
    assert "session_id: joke-subagent-1" not in result
    assert runtime.run_calls[0]["session_id"] == "sess_task_non_blocking_1"
    assert runtime.created == 1


def test_task_rejects_non_boolean_run_in_background(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    with pytest.raises(ToolError, match="run_in_background must be a boolean"):
        tool.run(
            {
                "run_in_background": "true",
                "load_skills": [],
                "description": "delegate task",
                "prompt": "do work",
                "subagent_type": "oracle",
            },
            _context(tmp_path),
        )
