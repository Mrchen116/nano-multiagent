import asyncio
from dataclasses import dataclass
from pathlib import Path

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
        return _Session(session_id=f"sess_task_blocking_{self.created}")

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
            turn_id="turn_blocking_integration",
            messages=(Message(message_id="msg_blocking", role="assistant", content="task-ok"),),
            completed=True,
            stop_reason="completed",
        )

    async def continue_turn(self, session_id: str, *, stream: bool = True, llm_session_id: str | None = None) -> TurnResult:
        return await self.run(session_id, [{"type": "text", "text": "continue"}], stream=stream)


def test_task_blocking_runs_through_tool_registry_with_runtime_wiring(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    # Use an empty hook registry to avoid auto_mode_gate blocking the task tool
    # (task is not in SAFE_TOOL_ALLOWLIST but is a first-class builtin tool).
    app = create_app(runtime=runtime, repo_root=tmp_path, hook_registry=HookRegistry())
    # task tool is no longer in the default tool set; register and wire it explicitly.
    task_tool = TaskTool(runtime=runtime)
    app.state.tool_registry.register(task_tool)

    result = asyncio.run(app.state.tool_registry.execute(
        "task",
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "run integration",
            "prompt": "run integration task",
            "subagent_type": "oracle",
        },
        hook_context=HookContext(session_id="sess_main_integration", repo_root=tmp_path),
    ))

    # task tool now returns a structured object instead of a formatted string.
    assert result["status"] == "completed"
    assert result["content"] == "task-ok"
    assert result["sessionId"] == "sess_task_blocking_1"
    assert result["agent"] == "oracle"
    assert "durationMs" in result
    assert runtime.run_calls[0]["stream"] is False
