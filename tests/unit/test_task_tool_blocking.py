from dataclasses import dataclass
from pathlib import Path

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

    async def create_session(
        self,
        *,
        workspace_root: Path,
        title: str | None = None,
        system_prompt: str | None = None,
        skills: tuple[str, ...] | None = None,
        tool_allowlist: tuple[str, ...] | None = None,
        metadata=None,
    ) -> _Session:
        del workspace_root, title, system_prompt, skills, tool_allowlist, metadata
        self.created += 1
        return _Session(session_id=f"sess_task_{self.created}")

    async def run(
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

    async def continue_turn(self, session_id: str, *, stream: bool = True, llm_session_id: str | None = None, run_id: str | None = None) -> TurnResult:
        return await self.run(
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
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "run task",
            "prompt": "hello",
            "subagent_type": "oracle",
        },
        _context(tmp_path),
    )

    assert result.startswith("Task completed in ")
    assert "Agent: oracle" in result
    assert "\n---\n\ntask:hello\n" in result
    assert "<task_metadata>\nsession_id: sess_task_1\n</task_metadata>" in result
    assert runtime.run_calls[0]["stream"] is False


def test_task_blocking_wraps_subagent_errors_without_raising(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    result = tool.run(
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "run task",
            "prompt": "boom",
            "subagent_type": "oracle",
        },
        _context(tmp_path),
    )

    assert result.startswith("Task failed")
    assert "**Error**: subagent exploded" in result
    assert "<task_metadata>" in result
    assert "session_id: sess_task_1" in result
    assert "</task_metadata>" in result


def test_task_blocking_respects_timeout_seconds(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    result = tool.run(
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "run task",
            "prompt": "sleep",
            "subagent_type": "oracle",
            "timeout_seconds": 0.05,
        },
        _context(tmp_path),
    )

    assert result.startswith("Task timed out")
    assert "**Error**: task exceeded timeout_seconds=0.05" in result
    assert "<task_metadata>" in result
    assert "session_id: sess_task_1" in result
    assert "</task_metadata>" in result
