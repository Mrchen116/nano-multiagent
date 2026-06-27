"""Integration tests for agent continuation: message queue and JSONL rehydrate."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from agent.core.background_tasks.models import BackgroundTaskStatus
from agent.core.errors import ToolError
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.core.types import Message, TurnResult
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.tools.builtins.agent import AgentTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

from ._runtime_stub import _RuntimeStubBase, _make_ctx

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
        import time as _time

        if self._delay > 0:
            _time.sleep(self._delay)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_1",
            messages=(
                Message(message_id="msg_1", role="assistant", content="subagent done"),
            ),
            completed=True,
            stop_reason="completed",
        )


def test_message_queued_for_running_agent(tmp_path: Path) -> None:
    """Sending a prompt to a running agent queues it instead of launching a second run."""
    runtime = _RuntimeStub(tmp_path, delay=2.0)
    wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    tool = AgentTool(runtime=runtime, wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    # Launch background agent.
    result = tool.run(
        {
            "description": "long task",
            "prompt": "Take your time.",
            "subagent_type": "oracle",
            "load_skills": [],
            "run_in_background": True,
        },
        ctx,
    )
    agent_id = result["agent_id"]

    # Send follow-up while still running.
    follow_up = tool.run(
        {
            "agent_id": agent_id,
            "prompt": "Also check the tests.",
        },
        ctx,
    )

    assert follow_up["status"] == "message_queued"
    assert follow_up["agent_id"] == agent_id

    # Pending messages should be in registry.
    pending = wiring.registry.drain_agent_messages(agent_id)
    assert pending == ("Also check the tests.",)


def test_jsonl_rehydrate_continues_agent_after_registry_loss(tmp_path: Path) -> None:
    """After kernel restart (registry lost), Agent(agent_id=...) rehydrates from session store."""
    runtime = _RuntimeStub(tmp_path, delay=0.1)
    wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    tool = AgentTool(runtime=runtime, wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    # Launch background agent and let it complete.
    result = tool.run(
        {
            "description": "research",
            "prompt": "Study loop.",
            "subagent_type": "explore",
            "load_skills": [],
            "run_in_background": True,
        },
        ctx,
    )
    agent_id = result["agent_id"]

    for _ in range(50):
        record = wiring.registry.get(agent_id)
        if record is not None and record.status.value in (
            "completed",
            "failed",
            "killed",
        ):
            break
        time.sleep(0.05)

    # Simulate kernel restart: create fresh registry but keep runtime (and its store).
    new_wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    new_tool = AgentTool(runtime=runtime, wiring=new_wiring)

    # Continue the agent — should rehydrate from JSONL (session store).
    resume_result = new_tool.run(
        {
            "agent_id": agent_id,
            "prompt": "Now focus on bash.",
        },
        ctx,
    )

    assert resume_result["status"] == "async_launched"
    assert resume_result["agent_id"] == agent_id

    # Fresh registry should now have the running record.
    record = new_wiring.registry.get(agent_id)
    assert record is not None
    assert record.status == BackgroundTaskStatus.RUNNING


def test_continuation_on_unknown_agent_id_raises_not_found(tmp_path: Path) -> None:
    """Agent(agent_id=unknown) with no store match returns ToolError."""
    runtime = _RuntimeStub(tmp_path)
    wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    tool = AgentTool(runtime=runtime, wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    with pytest.raises(ToolError, match="No subagent with agent_id"):
        tool.run(
            {
                "agent_id": "a000000000000000",
                "prompt": "Continue.",
            },
            ctx,
        )
