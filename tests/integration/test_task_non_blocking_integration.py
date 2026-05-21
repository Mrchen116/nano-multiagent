import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.tools.base import set_tool_safety_factory, set_tool_safety_config_factory
from agent.platform.http_api.app import create_app
from agent.core.types import Message, TurnResult
from agent.platform.persistence.session.service import SessionService
from agent.platform.tools.builtins.task import TaskTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class _RecordingLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
        self.requests.append(request)
        yield LLMMessage(role="assistant", content="subagent-ok")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _RuntimeStub:
    def __init__(self) -> None:
        self.created = 0
        self.run_calls: list[dict[str, object]] = []

    async def create_session(self, *, workspace_root=None, title=None, system_prompt=None, skills=None, tool_allowlist=None, metadata=None) -> _Session:
        self.created += 1
        return _Session(session_id=f"sess_non_blocking_integration_{self.created}")

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
            turn_id="turn_non_blocking_integration",
            messages=(Message(message_id="msg_non_blocking_integration", role="assistant", content="done"),),
            completed=True,
            stop_reason="completed",
        )

    async def continue_turn(self, session_id: str, *, stream: bool = True, llm_session_id: str | None = None) -> TurnResult:
        del stream, llm_session_id
        return await self.run(session_id, [{"type": "text", "text": "continue"}], stream=False)


def _wait_for(predicate, *, timeout_seconds: float = 0.6) -> None:  # noqa: ANN001
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met before timeout")


async def test_task_blocking_passes_parent_session_id_to_subagent_llm(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    llm_client = _RecordingLLMClient()
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=llm_client,
        model="mock-model",
    )
    # Use empty hook registry to avoid auto_mode_gate blocking the task tool.
    app = create_app(runtime=runtime, session_store=service.manager.store, repo_root=tmp_path, hook_registry=HookRegistry())
    task_tool = TaskTool(runtime=runtime)
    app.state.tool_registry.register(task_tool)

    result = await app.state.tool_registry.execute(
        "task",
        {
            "run_in_background": False,
            "load_skills": [],
            "description": "delegate task",
            "prompt": "delegate this",
            "category": "research",
        },
        hook_context=HookContext(session_id="sess_main_header", repo_root=tmp_path),
    )

    # task tool now returns a structured object.
    assert result["status"] == "completed"
    assert "sessionId" in result
    assert result["sessionId"] != "sess_main_header"  # subagent gets its own session
    assert llm_client.requests[0].session_id == "sess_main_header"


def test_task_non_blocking_executes_on_same_node_and_returns_receipt(tmp_path: Path) -> None:
    runtime = _RuntimeStub()
    app = create_app(runtime=runtime, repo_root=tmp_path, hook_registry=HookRegistry())
    task_tool = TaskTool(runtime=runtime)
    app.state.tool_registry.register(task_tool)

    result = asyncio.run(
        app.state.tool_registry.execute(
            "task",
            {
                "run_in_background": True,
                "load_skills": [],
                "description": "delegate task",
                "prompt": "run async",
                "subagent_type": "oracle",
            },
            hook_context=HookContext(session_id="sess_main_non_blocking", repo_root=tmp_path),
        )
    )

    # task tool now returns a structured object for background launches.
    assert result["status"] == "async_launched"
    assert result["sessionId"] == "sess_non_blocking_integration_1"
    assert result["agent"] == "oracle"
    _wait_for(lambda: len(runtime.run_calls) == 1)
