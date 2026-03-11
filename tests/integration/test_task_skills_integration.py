from dataclasses import dataclass
from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.types import Message, TurnResult
from agent.core.hooks.context import HookContext
from agent.platform.http_api.app import create_app


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0
        self.run_calls: list[dict[str, object]] = []

    def create_session(self) -> _Session:
        self.created += 1
        return _Session(session_id=f"sess_task_skills_{self.created}")

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
        return TurnResult(
            session_id=session_id,
            turn_id="turn_task_skills",
            messages=(Message(message_id="msg_task_skills", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


def test_task_new_task_requires_exactly_one_selector(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    app = create_app(runtime=runtime, repo_root=tmp_path)

    with pytest.raises(ToolError, match="either category or subagent_type is required"):
        app.state.tool_registry.execute(
            "task",
            {
                "run_in_background": False,
                "load_skills": [],
                "description": "delegate task",
                "prompt": "run task",
            },
            hook_context=HookContext(session_id="sess_main", repo_root=tmp_path),
        )


def test_task_continuation_can_skip_selector(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    app = create_app(runtime=runtime, repo_root=tmp_path)

    result = app.state.tool_registry.execute(
        "task",
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "continue task",
            "prompt": "follow up",
            "session_id": "sess_existing_task",
        },
        hook_context=HookContext(session_id="sess_main", repo_root=tmp_path),
    )

    assert "Task continued and completed" in result["result"]
    assert "session_id: sess_existing_task" in result["result"]
    assert runtime.created == 0


def test_task_rejects_unknown_load_skills_name(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    app = create_app(runtime=runtime, repo_root=tmp_path)

    with pytest.raises(ToolError, match="unknown skills requested"):
        app.state.tool_registry.execute(
            "task",
            {
                "run_in_background": False,
                "load_skills": ["skill-not-exist"],
                "description": "delegate task",
                "prompt": "run task",
                "subagent_type": "oracle",
            },
            hook_context=HookContext(session_id="sess_main", repo_root=tmp_path),
        )
