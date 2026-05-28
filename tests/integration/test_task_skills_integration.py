import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.types import Message, TurnResult
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.tools.base import set_tool_safety_factory, set_tool_safety_config_factory
from agent.platform.http_api.app import create_app
from agent.platform.tools.builtins.task import TaskTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0
        self.run_calls: list[dict[str, object]] = []

    async def create_session(self, *, workspace_root=None, title=None, system_prompt=None, skills=None, tool_allowlist=None, metadata=None) -> _Session:
        self.created += 1
        return _Session(session_id=f"sess_task_skills_{self.created}")

    async def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
        run_id: str | None = None,
        controller=None,
        parent_session_id: str | None = None,
        origin=None,
        workspace_root=None,
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

    async def continue_turn(self, session_id: str, *, stream: bool = True, llm_session_id: str | None = None) -> TurnResult:
        return await self.run(session_id, [{"type": "text", "text": "continue"}], stream=stream)


def _make_registry(tmp_path: Path, runtime: _RuntimeStub):
    # Use an empty hook registry to avoid auto_mode_gate blocking the task tool.
    app = create_app(runtime=runtime, repo_root=tmp_path, hook_registry=HookRegistry())
    task_tool = TaskTool(runtime=runtime)
    app.state.tool_registry.register(task_tool)
    return app.state.tool_registry


def test_task_new_task_requires_exactly_one_selector(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    registry = _make_registry(tmp_path, runtime)

    with pytest.raises(ToolError, match="either category or subagent_type is required"):
        asyncio.run(registry.execute(
            "task",
            {
                "run_in_background": False,
                "load_skills": [],
                "description": "delegate task",
                "prompt": "run task",
            },
            hook_context=HookContext(session_id="sess_main", repo_root=tmp_path),
        ))


def test_task_continuation_can_skip_selector(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    registry = _make_registry(tmp_path, runtime)

    result = asyncio.run(registry.execute(
        "task",
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "continue task",
            "prompt": "follow up",
            "session_id": "sess_existing_task",
        },
        hook_context=HookContext(session_id="sess_main", repo_root=tmp_path),
    ))

    # task tool now returns a structured object.
    assert result["status"] == "completed"
    assert result["sessionId"] == "sess_existing_task"
    assert result["continuation"] is True
    assert runtime.created == 0


def test_task_rejects_unknown_load_skills_name(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    registry = _make_registry(tmp_path, runtime)

    with pytest.raises(ToolError, match="unknown skills requested"):
        asyncio.run(registry.execute(
            "task",
            {
                "run_in_background": False,
                "load_skills": ["skill-not-exist"],
                "description": "delegate task",
                "prompt": "run task",
                "subagent_type": "oracle",
            },
            hook_context=HookContext(session_id="sess_main", repo_root=tmp_path),
        ))
