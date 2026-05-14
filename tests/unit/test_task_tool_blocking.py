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
        workspace_root=None,
        parent_session_id: str | None = None,
        run_id: str | None = None,
        controller=None,
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

    async def continue_turn(self, session_id: str, *, stream: bool = True, llm_session_id: str | None = None, run_id: str | None = None, workspace_root=None) -> TurnResult:
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

    assert result["status"] == "completed"
    assert result["content"] == "task:hello"
    assert result["agent"] == "oracle"
    assert result["continuation"] is False
    assert "sessionId" in result
    assert "taskId" in result
    assert "durationMs" in result

    serialized = tool.serialize_result(result)
    assert serialized.startswith("Task completed in ")
    assert "Agent: oracle" in serialized
    assert "\n---\n\ntask:hello\n" in serialized
    assert "session_id: sess_task_1" in serialized
    assert "task_id:" in serialized
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

    assert result["status"] == "failed"
    assert result["title"] == "Task failed"
    assert result["error"] == "subagent exploded"
    assert result["agent"] == "oracle"
    assert "sessionId" in result

    serialized = tool.serialize_result(result)
    assert serialized.startswith("Task failed")
    assert "Error: subagent exploded" in serialized
    assert "session_id: sess_task_1" in serialized


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

    assert result["status"] == "failed"
    assert result["title"] == "Task timed out"
    assert "timeout_seconds=0.05" in result["error"]
    assert result["agent"] == "oracle"
    assert "sessionId" in result

    serialized = tool.serialize_result(result)
    assert serialized.startswith("Task timed out")
    assert "Error: task exceeded timeout_seconds=0.05" in serialized
    assert "session_id: sess_task_1" in serialized


def test_task_blocking_serialize_result_with_empty_content(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    tool = TaskTool(runtime=runtime)

    result = {
        "status": "completed",
        "content": "",
        "sessionId": "sess_empty",
        "durationMs": 42,
        "agent": "test",
        "continuation": False,
        "taskId": "tid_empty",
    }
    serialized = tool.serialize_result(result)
    assert "(Subagent completed but returned no output.)" in serialized
    assert "session_id: sess_empty" in serialized
