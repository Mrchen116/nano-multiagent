"""Integration tests for task_stop over wired background-task state."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from agent.core.background_tasks.models import BackgroundTaskStatus
from agent.core.errors import ToolError
from agent.core.tools.base import (
    set_tool_safety_config_factory,
    set_tool_safety_factory,
)
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.builtins.task_stop import TaskStopTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

from ._runtime_stub import _RunsRegistryStub, _make_ctx

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def test_task_stop_kills_running_bash_task(tmp_path: Path) -> None:
    runs = _RunsRegistryStub()
    wiring = wire_background_tasks(workspace_root=tmp_path, runs_registry=runs)
    bash_tool = BashTool(wiring=wiring)
    stop_tool = TaskStopTool(wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    result = bash_tool.run(
        {
            "command": "sleep 30",
            "description": "long sleep",
            "run_in_background": True,
        },
        ctx,
    )
    task_id = result["task_id"]

    stop_result = stop_tool.run({"task_id": task_id}, ctx)

    assert stop_result["status"] == "killed"
    record = wiring.registry.get(task_id)
    assert record is not None
    assert record.status == BackgroundTaskStatus.KILLED
    assert record.notified is True
    assert runs.submissions == []
    assert runs.injections == []


def test_task_stop_signals_subagent_without_winning_terminal_race(
    tmp_path: Path,
) -> None:
    wiring = wire_background_tasks(workspace_root=tmp_path)
    stop_tool = TaskStopTool(wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    class _Handle:
        stopped = False

        def stop(self) -> None:
            self.stopped = True

    handle = _Handle()
    agent_id = "a-subagent"
    wiring.registry.register_subagent(
        task_id=agent_id,
        parent_session_id="sess_parent",
        agent_id=agent_id,
        agent_session_id="subagent-session",
        description="inspect",
        prompt="inspect",
        agent_type="explore",
        output_file=str(tmp_path / "subagent.jsonl"),
    )
    wiring.registry.mark_running(agent_id)
    wiring.registry.set_stop_handle(agent_id, handle)

    result = stop_tool.run({"task_id": agent_id}, ctx)

    assert result["status"] == "killed"
    assert handle.stopped is True
    assert wiring.registry.get(agent_id).status == BackgroundTaskStatus.RUNNING

    wiring.registry.kill(
        agent_id,
        reason="stopped by user",
        result_text="partial findings",
    )
    record = wiring.registry.get(agent_id)
    assert record is not None
    assert record.status == BackgroundTaskStatus.KILLED
    assert record.result_text == "partial findings"


def test_task_stop_on_already_terminal_raises_error(tmp_path: Path) -> None:
    wiring = wire_background_tasks(workspace_root=tmp_path)
    bash_tool = BashTool(wiring=wiring)
    stop_tool = TaskStopTool(wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    result = bash_tool.run(
        {
            "command": "echo done",
            "description": "quick cmd",
            "run_in_background": True,
        },
        ctx,
    )
    task_id = result["task_id"]
    for _ in range(50):
        record = wiring.registry.get(task_id)
        if record is not None and record.status in {
            BackgroundTaskStatus.COMPLETED,
            BackgroundTaskStatus.FAILED,
            BackgroundTaskStatus.KILLED,
        }:
            break
        time.sleep(0.05)

    with pytest.raises(ToolError, match="already completed"):
        stop_tool.run({"task_id": task_id}, ctx)
