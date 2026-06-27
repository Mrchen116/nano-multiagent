"""Integration tests for foreground auto-backgrounding (bash 15s, agent 120s)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.core.types import Message, TurnResult
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.tools.builtins.agent import AgentTool
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

from ._runtime_stub import _RunsRegistryStub, _RuntimeStubBase, _make_ctx

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class _RuntimeStub(_RuntimeStubBase):
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
        model: str | None = None,
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
