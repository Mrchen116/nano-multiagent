"""Integration tests for foreground auto-backgrounding (bash 15s, agent 120s)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

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
        llm_session_id: str | None = None,
    ) -> TurnResult:
        import time

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

    def resolve_available_skills(
        self, workspace_root: Any, include_names: Any = None
    ) -> tuple:
        return ()


class _RunsRegistryStub:
    def __init__(self) -> None:
        self.submissions: list[dict[str, Any]] = []
        self.injections: list[dict[str, Any]] = []
        self._active_run_by_session: dict[str, str] = {}

    def get_active_run_id(self, session_id: str) -> str | None:
        return self._active_run_by_session.get(session_id)

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
    ) -> Any:
        self.submissions.append(
            {
                "session_id": session_id,
                "parts": parts,
                "origin": origin,
                "source_task_id": source_task_id,
            }
        )
        return type(
            "RunRecord",
            (),
            {"run_id": "run_1", "session_id": session_id, "status": "queued"},
        )()


def _make_ctx(tmp_path: Path, session_id: str = "sess_parent") -> ToolContext:
    return ToolContext.create(repo_root=tmp_path).with_session(session_id=session_id)


def test_bash_foreground_auto_backgrounds_after_budget_timeout(tmp_path: Path) -> None:
    """Foreground bash exceeding the budget auto-backgrounds and returns receipt."""
    import agent.platform.tools.builtins.bash as bash_module

    original_budget = bash_module._DEFAULT_FOREGROUND_BUDGET
    bash_module._DEFAULT_FOREGROUND_BUDGET = 0.1
    try:
        wiring = wire_background_tasks(workspace_root=tmp_path)
        tool = BashTool(wiring=wiring)
        ctx = _make_ctx(tmp_path, session_id="sess_parent")

        result = tool.run(
            {
                "command": "sleep 0.5",
                "description": "slow cmd",
                "run_in_background": False,
            },
            ctx,
        )

        # Should auto-background, not raise or return synchronous result.
        assert result["status"] == "async_launched"
        assert result["task_id"].startswith("b")
        assert "output_file" in result
    finally:
        bash_module._DEFAULT_FOREGROUND_BUDGET = original_budget


def test_agent_foreground_auto_backgrounds_after_budget_timeout(tmp_path: Path) -> None:
    """Foreground agent exceeding the budget auto-backgrounds and returns receipt."""
    import agent.platform.tools.builtins.agent as agent_module

    original_budget = agent_module._DEFAULT_FOREGROUND_BUDGET
    agent_module._DEFAULT_FOREGROUND_BUDGET = 0.1
    try:
        runtime = _RuntimeStub(tmp_path, delay=0.5)
        wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
        tool = AgentTool(runtime=runtime, wiring=wiring)
        ctx = _make_ctx(tmp_path, session_id="sess_parent")

        result = tool.run(
            {
                "description": "slow agent",
                "prompt": "Take your time.",
                "subagent_type": "oracle",
                "load_skills": [],
                "run_in_background": False,
            },
            ctx,
        )

        # Should auto-background.
        assert result["status"] == "async_launched"
        assert result["agent_id"].startswith("a")
        assert "output_file" in result
    finally:
        agent_module._DEFAULT_FOREGROUND_BUDGET = original_budget
