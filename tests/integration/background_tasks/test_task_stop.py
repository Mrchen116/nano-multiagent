"""Integration tests for task_stop against background bash and agent tasks."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from agent.core.background_tasks.models import BackgroundTaskStatus
from agent.core.errors import ToolError
from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.origin import RunOrigin
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.core.types import Message, TurnResult
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.agent import AgentTool
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.builtins.task_stop import TaskStopTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class _FakeStore:
    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path
        self._sessions: dict[str, dict[str, Any]] = {}

    def resolve_path(
        self, session_id: str, *, workspace_root=None, parent_session_id: str = ""
    ) -> Path:
        path = self._tmp_path / "sessions" / f"{session_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def find_session_by_metadata(
        self, *, parent_session_id: str, match: dict[str, Any], workspace_root=None
    ) -> str | None:
        for sid, meta in self._sessions.items():
            if all(meta.get(k) == v for k, v in match.items()):
                return sid
        return None


class _SessionManagerStub:
    def __init__(self, store: _FakeStore) -> None:
        self.store = store

    def load(
        self, session_id: str, *, workspace_root=None, parent_session_id: str = ""
    ) -> Any:
        meta = self.store._sessions.get(session_id, {})
        return type(
            "LoadResult",
            (),
            {
                "config": type("Config", (), {"metadata": meta})(),
            },
        )()


class _RuntimeStub:
    def __init__(self, tmp_path: Path, delay: float = 0.0) -> None:
        self._tmp_path = tmp_path
        self._delay = delay
        self._counter = 0
        store = _FakeStore(tmp_path)
        self._session_manager = _SessionManagerStub(store)

    async def create_session(
        self,
        *,
        workspace_root: Any = None,
        skills: Any = None,
        metadata: Any = None,
        parent_session_id: str | None = None,
    ) -> Any:
        self._counter += 1
        sid = f"subagent_{self._counter}"
        self._session_manager.store._sessions[sid] = dict(metadata or {})
        return type("Session", (), {"session_id": sid})()

    def session_workspace_root(self, session_id: str) -> Any:
        return self._tmp_path

    async def run(
        self,
        session_id: str,
        parts: Any,
        *,
        stream: bool = False,
        controller: Any = None,
        parent_session_id: str | None = None,
        workspace_root: Any = None,
        run_id: str | None = None,
    ) -> TurnResult:
        if self._delay > 0:
            time.sleep(self._delay)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_1",
            messages=(
                Message(message_id="msg_1", role="assistant", content="subagent done"),
            ),
            completed=True,
            stop_reason="completed",
        )


class _RunsRegistryStub:
    def __init__(self) -> None:
        self.submissions: list[dict[str, Any]] = []
        self.injections: list[dict[str, Any]] = []
        self._active_run_by_session: dict[str, str] = {}

    def get_active_run_id(self, session_id: str) -> str | None:
        return self._active_run_by_session.get(session_id)

    def get_event_loop(self) -> Any | None:
        return None

    @property
    def session_manager(self) -> None:
        # bugfix-404 F3: stub satisfies the public property added to RunsRegistry.
        return None

    def inject_pending_message(self, session_id: str, message: LLMMessage) -> bool:
        self.injections.append({"session_id": session_id, "message": message})
        return True

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict[str, Any]],
        origin: RunOrigin = RunOrigin.USER,
        source_task_id: str | None = None,
        trace_id: str | None = None,
        workspace_root: Any = None,
    ) -> Any:
        self.submissions.append(
            {
                "session_id": session_id,
                "parts": parts,
                "origin": origin,
                "source_task_id": source_task_id,
                "workspace_root": workspace_root,
            }
        )
        return type(
            "RunRecord",
            (),
            {"run_id": "run_1", "session_id": session_id, "status": "queued"},
        )()


def _make_ctx(tmp_path: Path, session_id: str = "sess_parent") -> ToolContext:
    return ToolContext.create(repo_root=tmp_path).with_session(session_id=session_id)


def test_task_stop_kills_running_bash_task(tmp_path: Path) -> None:
    runs = _RunsRegistryStub()
    wiring = wire_background_tasks(workspace_root=tmp_path, runs_registry=runs)
    bash_tool = BashTool(wiring=wiring)
    stop_tool = TaskStopTool(wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    # Launch a long-running background bash.
    result = bash_tool.run(
        {
            "command": "sleep 30",
            "description": "long sleep",
            "run_in_background": True,
        },
        ctx,
    )
    task_id = result["task_id"]

    # Verify running.
    record = wiring.registry.get(task_id)
    assert record is not None
    assert record.status == BackgroundTaskStatus.RUNNING

    # Stop it.
    stop_result = stop_tool.run({"task_id": task_id}, ctx)
    assert stop_result["status"] == "killed"
    assert stop_result["task_id"] == task_id

    # Registry should be killed.
    record = wiring.registry.get(task_id)
    assert record is not None
    assert record.status == BackgroundTaskStatus.KILLED

    # Notification delivered.
    assert len(runs.submissions) == 1
    assert runs.submissions[0]["origin"] == RunOrigin.BACKGROUND_TASK
    assert "killed" in runs.submissions[0]["parts"][0]["text"]


def test_task_stop_kills_running_agent_task(tmp_path: Path) -> None:
    runtime = _RuntimeStub(tmp_path, delay=30.0)
    runs = _RunsRegistryStub()
    wiring = wire_background_tasks(
        workspace_root=tmp_path, runtime=runtime, runs_registry=runs
    )
    agent_tool = AgentTool(runtime=runtime, wiring=wiring)
    stop_tool = TaskStopTool(wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    result = agent_tool.run(
        {
            "description": "long agent",
            "prompt": "Sleep for a while.",
            "subagent_type": "oracle",
            "load_skills": [],
            "run_in_background": True,
        },
        ctx,
    )
    agent_id = result["agent_id"]

    # Verify running.
    record = wiring.registry.get(agent_id)
    assert record is not None
    assert record.status == BackgroundTaskStatus.RUNNING

    # Stop it.
    stop_result = stop_tool.run({"task_id": agent_id}, ctx)
    assert stop_result["status"] == "killed"
    assert stop_result["task_id"] == agent_id

    record = wiring.registry.get(agent_id)
    assert record is not None
    assert record.status == BackgroundTaskStatus.KILLED

    # Notification delivered.
    assert len(runs.submissions) == 1
    assert runs.submissions[0]["origin"] == RunOrigin.BACKGROUND_TASK


def test_task_stop_on_already_terminal_raises_error(tmp_path: Path) -> None:
    runs = _RunsRegistryStub()
    wiring = wire_background_tasks(workspace_root=tmp_path, runs_registry=runs)
    bash_tool = BashTool(wiring=wiring)
    stop_tool = TaskStopTool(wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    # Launch a quick command that completes immediately.
    result = bash_tool.run(
        {
            "command": "echo done",
            "description": "quick cmd",
            "run_in_background": True,
        },
        ctx,
    )
    task_id = result["task_id"]

    # Wait for completion.
    for _ in range(50):
        record = wiring.registry.get(task_id)
        if record is not None and record.status.value in (
            "completed",
            "failed",
            "killed",
        ):
            break
        time.sleep(0.05)

    # Stopping a terminal task should raise ToolError.
    with pytest.raises(ToolError, match="already completed"):
        stop_tool.run({"task_id": task_id}, ctx)
