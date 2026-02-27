from dataclasses import dataclass
from pathlib import Path

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

    def create_session(self) -> _Session:
        self.created += 1
        return _Session(session_id=f"sess_task_{self.created}")

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
        text = parts[0]["text"]
        if text == "boom":
            raise ValueError("subagent exploded")
        if text == "sleep":
            import time

            time.sleep(0.2)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_task",
            messages=(Message(message_id="msg_task", role="assistant", content=f"task:{text}"),),
            completed=True,
            stop_reason="completed",
        )

    def continue_turn(self, session_id: str, *, stream: bool = True, llm_session_id: str | None = None) -> TurnResult:
        return self.run(
            session_id,
            [{"type": "text", "text": "continue"}],
            stream=stream,
            llm_session_id=llm_session_id,
        )


def _context(tmp_path: Path) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path)


def test_task_blocking_returns_structured_success_payload(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    result = tool.run(
        {"mode": "blocking", "prompt": "hello", "subagent_type": "oracle"},
        _context(tmp_path),
    )

    assert result["mode"] == "blocking"
    assert result["status"] == "completed"
    assert result["session_id"] == "sess_task_1"
    assert result["output"]["message"]["content"] == "task:hello"
    assert result["duration_ms"] >= 0
    assert runtime.run_calls[0]["stream"] is False


def test_task_blocking_wraps_subagent_errors_without_raising(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    result = tool.run(
        {"mode": "blocking", "prompt": "boom", "subagent_type": "oracle"},
        _context(tmp_path),
    )

    assert result["mode"] == "blocking"
    assert result["status"] == "failed"
    assert result["error"]["code"] == "task_execution_failed"
    assert "subagent exploded" in result["error"]["message"]


def test_task_blocking_respects_timeout_seconds(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    result = tool.run(
        {
            "mode": "blocking",
            "prompt": "sleep",
            "subagent_type": "oracle",
            "timeout_seconds": 0.05,
        },
        _context(tmp_path),
    )

    assert result["mode"] == "blocking"
    assert result["status"] == "timed_out"
    assert result["error"]["code"] == "task_timeout"
